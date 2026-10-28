package io.github.bitpindev.bitpin;

import static io.github.bitpindev.bitpin.TestSupport.T_ORDER;
import static io.github.bitpindev.bitpin.TestSupport.env;
import static io.github.bitpindev.bitpin.TestSupport.map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import io.github.bitpindev.bitpin.TestSupport.Env;
import io.github.bitpindev.bitpin.TestSupport.Reply;
import io.github.bitpindev.bitpin.TestSupport.Route;
import java.io.IOException;
import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class WalletTest {
  @Test
  void balancesWalkEveryPage() {
    Env e = env();
    Route wallets = e.http().endpoint("private_get_wlt_wallets");
    Balances bal = e.client().fetchBalance();
    assertEquals("main", wallets.last().query().get("service"));
    assertEquals("1000", wallets.last().query().get("limit"));
    assertEquals("0.0135", bal.get("BTC").total().toPlainString());
    assertEquals(BigDecimal.ZERO, bal.get("NONE").total());

    List<Object> page1 = new ArrayList<>();
    for (int i = 0; i < 1000; i++) {
      page1.add(
          map("id", String.valueOf(1000 + i), "asset", "C" + i, "balance", "1", "frozen", "0"));
    }
    Route paged =
        e.http()
            .on(
                "GET",
                "/api/v1/wlt/wallets/",
                Reply.of(200, page1),
                Reply.of(200, Fixtures.body("private_get_wlt_wallets")));
    Balances all = e.client().fetchBalance(Map.of("service", "stake"));
    assertEquals(2, paged.count());
    assertEquals("stake", paged.at(0).query().get("service"));
    assertEquals("1000", paged.at(1).query().get("offset"));
    assertTrue(all.currencies().containsKey("C999"));
  }

  @Test
  void addressesAccountsNetworks() {
    Env e = env();
    e.http().endpoint("private_get_wlt_account_numbers");
    assertEquals("123", e.client().fetchBankAccounts().get(0).id());
    Route addr = e.http().endpoint("private_post_wlt_address");
    assertEquals("TRX", e.client().fetchDepositAddress("usdt", "trx").network());
    assertEquals(map("currency", "USDT", "network", "TRX"), addr.last().body());
    assertThrows(BadRequestException.class, () -> e.client().fetchDepositAddress("USDT", ""));
    assertThrows(BadRequestException.class, () -> e.client().fetchDepositAddress("USDT", null));
    Route nets = e.http().endpoint("private_get_wlt_networks");
    List<Network> got = e.client().fetchCurrencyNetworks("usdt");
    assertEquals("USDT", nets.last().query().get("currency_code"));
    assertFalse(got.get(0).withdraw());
    assertTrue(got.get(1).withdraw());
  }

  @Test
  void depositsAndWithdrawals() {
    Env e = env();
    Route deps = e.http().endpoint("private_get_wlt_deposits");
    List<Transaction> d = e.client().fetchDeposits("usdt", T_ORDER, 10, null);
    assertEquals("USDT", deps.last().query().get("currency"));
    assertEquals("2026-10-27T06:45:30.123+00:00", deps.last().query().get("start"));
    assertEquals("ok", d.get(0).status());
    e.client().fetchDeposits(null, null, null, Map.of("paginate", true));
    assertEquals("1000", deps.last().query().get("limit"));
    Route wd = e.http().endpoint("private_get_wlt_withdraws");
    assertEquals(2, e.client().fetchWithdrawals("USDT", T_ORDER, null, null).size());
    assertEquals("2026-10-27", wd.last().query().get("start"));
    e.client().fetchWithdrawals();
    assertFalse(wd.last().query().containsKey("start"));
  }

  @Test
  void withdrawBuildsEachKind() {
    Env e = env();
    Route create = e.http().endpoint("private_post_wlt_withdraws");
    Transaction w =
        e.client().withdraw("USDT", new BigDecimal("50"), "TAddr", null, Map.of("network", "trx"));
    assertEquals(
        map("currency", "USDT", "amount", "50", "address", "TAddr", "network", "TRX"),
        create.last().body());
    assertEquals(
        List.of("7003", "pending", false),
        List.of(w.id(), w.status(), w.info().get("is_single_otp")));
    e.client().withdraw("XRP", BigDecimal.TEN, "rTest", "12345", Map.of("network", "XRP"));
    assertEquals("12345", ((Map<?, ?>) create.last().body()).get("memo"));
    e.client().withdraw("IRT", new BigDecimal("5000000"), null, null, Map.of("accountNumber", 123));
    assertEquals(
        map("currency", "IRT", "amount", "5000000", "account_number", "123"), create.last().body());
    e.client()
        .withdraw(
            "USDT",
            BigDecimal.ONE,
            "",
            "",
            Map.of("alternativeAddress", "user@example.com", "extra", "x"));
    assertEquals(
        map(
            "currency",
            "USDT",
            "amount",
            "1",
            "alternative_address",
            "user@example.com",
            "extra",
            "x"),
        create.last().body());

    int before = create.count();
    assertThrows(
        BadRequestException.class,
        () -> e.client().withdraw("USDT", BigDecimal.ONE, "addr", null, null));
    assertThrows(
        BadRequestException.class,
        () -> e.client().withdraw("USDT", BigDecimal.ONE, "", null, null));
    assertThrows(
        BadRequestException.class,
        () -> e.client().withdraw("USDT", BigDecimal.ZERO, "a", null, Map.of("network", "TRX")));
    assertThrows(
        BadRequestException.class,
        () -> e.client().withdraw("USDT", null, "a", null, Map.of("network", "TRX")));
    assertEquals(before, create.count());

    Env never = env();
    Route down =
        never.http().on("POST", "/api/v2/wlt/withdraws/", Reply.fail(new IOException("down")));
    assertThrows(
        NetworkException.class,
        () -> never.client().withdraw("USDT", BigDecimal.ONE, "a", null, Map.of("network", "TRX")));
    assertEquals(1, down.count(), "withdrawals are never retried");
  }

  @Test
  void otp() {
    Env e = env();
    Route verify = e.http().endpoint("private_post_wlt_withdraws_verify_otp_id");
    assertEquals(map("detail", "success"), e.client().verifyWithdrawOtp("7003", "123456", false));
    assertEquals(map("otp", "123456", "is_second_otp", false), verify.last().body());
    assertEquals("/api/v1/wlt/withdraws/verify/otp/7003/", verify.last().path());
    e.http()
        .endpoint(
            "private_post_wlt_withdraws_verify_otp_id", Reply.of(400, map("code", "extra_try")));
    InvalidOtpException ex =
        assertThrows(InvalidOtpException.class, () -> e.client().verifyWithdrawOtp("1", "0", true));
    assertEquals("extra_try", ex.code());
    Route retry = e.http().endpoint("private_post_wlt_withdraws_retry_id");
    e.client().resendWithdrawOtp("7003", false, true);
    assertEquals(map("first", false, "use_voice_call", true), retry.last().body());
  }
}
