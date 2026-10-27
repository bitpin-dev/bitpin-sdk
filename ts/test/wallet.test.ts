import { describe, expect, it } from "vitest";
import { Decimal, errors } from "../src/index.js";
import { body, setup } from "./helpers.js";

describe("wallet", () => {
  it("balance reads every page", async () => {
    const { client, mock } = setup();
    const wallets = mock.endpoint("private_get_wlt_wallets");
    const balance = await client.fetchBalance();
    expect([
      wallets.last.url.searchParams.get("service"),
      wallets.last.url.searchParams.get("limit"),
    ]).toEqual(["main", "1000"]);
    expect(balance.BTC.total.toString()).toBe("0.0135");
    const rows = body("private_get_wlt_wallets");
    const page1 = Array.from({ length: 1000 }, (_, i) => ({
      ...rows[0],
      id: 1000 + i,
      asset: `C${i}`,
    }));
    const paged = mock.on("GET", "/api/v1/wlt/wallets/", [
      { status: 200, body: page1 },
      { status: 200, body: rows },
    ]);
    const all = await client.fetchBalance({ service: "stake" });
    expect(paged.count).toBe(2);
    expect(paged.calls[0]!.url.searchParams.get("service")).toBe("stake");
    expect(paged.calls[1]!.url.searchParams.get("offset")).toBe("1000");
    expect("C999" in all && "BTC" in all).toBe(true);
  });

  it("bank accounts, addresses and networks", async () => {
    const { client, mock } = setup();
    mock.endpoint("private_get_wlt_account_numbers");
    expect((await client.fetchBankAccounts())[0]!.id).toBe("123");
    const address = mock.endpoint("private_post_wlt_address");
    expect((await client.fetchDepositAddress("usdt", "trx")).network).toBe("TRX");
    expect(address.last.body).toEqual({ currency: "USDT", network: "TRX" });
    await client.fetchDepositAddress("USDT", undefined, { network: "TRX" });
    expect(address.last.body.network).toBe("TRX");
    await expect(client.fetchDepositAddress("USDT")).rejects.toThrow(/network/);
    const networks = mock.endpoint("private_get_wlt_networks");
    const result = await client.fetchCurrencyNetworks("usdt");
    expect(networks.last.url.searchParams.get("currency_code")).toBe("USDT");
    expect(Object.fromEntries(result.map((n) => [n.network, n.withdraw]))).toEqual({
      TRX: false,
      ETH: true,
    });
  });

  it("deposits and withdrawals", async () => {
    const { client, mock } = setup();
    const deposits = mock.endpoint("private_get_wlt_deposits");
    const dep = await client.fetchDeposits("usdt", 1793083530123, 10);
    expect([
      deposits.last.url.searchParams.get("currency"),
      deposits.last.url.searchParams.get("start"),
    ]).toEqual(["USDT", "2026-10-27T06:45:30.123+00:00"]);
    expect(dep[0]!.status).toBe("ok");
    await client.fetchDeposits(undefined, undefined, undefined, { paginate: true });
    expect(deposits.last.url.searchParams.get("limit")).toBe("1000");
    const withdraws = mock.endpoint("private_get_wlt_withdraws");
    expect((await client.fetchWithdrawals("USDT", 1793083530123)).map((w) => w.id)).toEqual([
      "7001",
      "7002",
    ]);
    expect(withdraws.last.url.searchParams.get("start")).toBe("2026-10-27");
    await client.fetchWithdrawals();
  });

  it("withdraw kinds and validation", async () => {
    const { client, mock } = setup();
    const create = mock.endpoint("private_post_wlt_withdraws");
    const w = await client.withdraw("USDT", new Decimal(50), "TAddr", null, { network: "trx" });
    expect(create.last.body).toEqual({
      currency: "USDT",
      amount: "50",
      address: "TAddr",
      network: "TRX",
    });
    expect([w.id, w.status, w.info.is_single_otp]).toEqual(["7003", "pending", false]);
    await client.withdraw("XRP", 10, "rTest", "12345", { network: "XRP" });
    expect(create.last.body.memo).toBe("12345");
    await client.withdraw("IRT", 5000000, null, null, { accountNumber: 123 });
    expect(create.last.body).toEqual({ currency: "IRT", amount: "5000000", account_number: "123" });
    await client.withdraw("USDT", 1, null, null, { alternativeAddress: "user@example.com" });
    expect(create.last.body).toEqual({
      currency: "USDT",
      amount: "1",
      alternative_address: "user@example.com",
    });
    const before = create.count;
    await expect(client.withdraw("USDT", 1, "addr")).rejects.toThrow(/network/);
    await expect(client.withdraw("USDT", 1)).rejects.toThrow(/address/);
    await expect(client.withdraw("USDT", 0, "a", null, { network: "TRX" })).rejects.toThrow(
      /amount/,
    );
    expect(create.count).toBe(before);
  });

  it("withdraw is never retried", async () => {
    const { client, mock } = setup();
    const create = mock.on("POST", "/api/v2/wlt/withdraws/", new TypeError("fetch failed"));
    await expect(client.withdraw("USDT", 1, "a", null, { network: "TRX" })).rejects.toBeInstanceOf(
      errors.NetworkError,
    );
    expect(create.count).toBe(1);
  });

  it("OTP verify and resend", async () => {
    const { client, mock } = setup();
    const verify = mock.endpoint("private_post_wlt_withdraws_verify_otp_id");
    expect(await client.verifyWithdrawOtp(7003, "123456")).toEqual({ detail: "success" });
    expect(verify.last.body).toEqual({ otp: "123456", is_second_otp: false });
    await client.verifyWithdrawOtp(7003, "654321", true);
    expect(verify.last.body.is_second_otp).toBe(true);
    expect(verify.last.url.pathname).toBe("/api/v1/wlt/withdraws/verify/otp/7003/");
    mock.endpoint("private_post_wlt_withdraws_verify_otp_id", {
      status: 400,
      body: { code: "extra_try" },
    });
    const error = await client.verifyWithdrawOtp(1, "000000").catch((e) => e);
    expect([error.constructor, error.code]).toEqual([errors.InvalidOTP, "extra_try"]);
    const retry = mock.endpoint("private_post_wlt_withdraws_retry_id");
    await client.resendWithdrawOtp(7003);
    expect(retry.last.body).toEqual({ first: true, use_voice_call: false });
    await client.resendWithdrawOtp(7003, false, true);
    expect(retry.last.body).toEqual({ first: false, use_voice_call: true });
  });
});
