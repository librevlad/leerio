package com.leerio.app;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.net.Uri;
import com.android.billingclient.api.AcknowledgePurchaseParams;
import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryPurchasesParams;
import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;

/**
 * Leerio Pro through Google Play Billing: the subscription's offers, the purchase, and whether Pro
 * is active. Checked on the phone (no server) and acknowledged here, so Play does not refund it.
 *
 * Calls never fail for normal states: no Play Store, offline or an unknown product resolve with
 * {@code available: false}. Event "entitlement" ({@code active}) — a purchase finished outside a
 * purchase() call, e.g. a pending payment went through.
 */
@CapacitorPlugin(name = "PlayBilling")
public class PlayBillingPlugin extends Plugin implements PurchasesUpdatedListener {

    private interface Task {
        void run(BillingResult setup);
    }

    private BillingClient client;
    private final List<Task> waiting = new ArrayList<>();
    private boolean connecting;

    /** Last product details per product id — purchase() launches from these */
    private final java.util.Map<String, ProductDetails> details = new java.util.HashMap<>();
    private PluginCall purchaseCall;
    private String productId = "leerio_pro";

    @Override
    public void load() {
        client = BillingClient.newBuilder(getContext())
            .setListener(this)
            .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
            .enableAutoServiceReconnection()
            .build();
    }

    @Override
    protected void handleOnDestroy() {
        if (client != null) client.endConnection();
    }

    // ── Connection ─────────────────────────────────────────────────────

    /** Runs the task once Play Billing is connected (or with the failed setup result) */
    private void withClient(Task task) {
        if (client.isReady()) {
            task.run(ok());
            return;
        }
        boolean start;
        synchronized (this) {
            waiting.add(task);
            start = !connecting;
            connecting = true;
        }
        if (!start) return;
        client.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult result) {
                flush(result);
            }

            @Override
            public void onBillingServiceDisconnected() {
                flush(BillingResult.newBuilder().setResponseCode(BillingClient.BillingResponseCode.SERVICE_DISCONNECTED).build());
            }
        });
    }

    private void flush(BillingResult result) {
        List<Task> tasks;
        synchronized (this) {
            connecting = false;
            tasks = new ArrayList<>(waiting);
            waiting.clear();
        }
        for (Task t : tasks) t.run(result);
    }

    private static BillingResult ok() {
        return BillingResult.newBuilder().setResponseCode(BillingClient.BillingResponseCode.OK).build();
    }

    private static boolean isOk(BillingResult r) {
        return r.getResponseCode() == BillingClient.BillingResponseCode.OK;
    }

    private static JSObject unavailable(BillingResult r) {
        JSObject ret = new JSObject();
        ret.put("available", false);
        ret.put("code", r.getResponseCode());
        return ret;
    }

    // ── Offers ─────────────────────────────────────────────────────────

    @PluginMethod
    public void getOffers(PluginCall call) {
        String id = call.getString("productId", productId);
        productId = id;
        withClient(setup -> {
            if (!isOk(setup)) {
                call.resolve(unavailable(setup));
                return;
            }
            QueryProductDetailsParams params = QueryProductDetailsParams.newBuilder()
                .setProductList(Collections.singletonList(
                    QueryProductDetailsParams.Product.newBuilder()
                        .setProductId(id)
                        .setProductType(BillingClient.ProductType.SUBS)
                        .build()))
                .build();
            client.queryProductDetailsAsync(params, (r, result) -> {
                if (!isOk(r)) {
                    call.resolve(unavailable(r));
                    return;
                }
                JSArray offers = new JSArray();
                for (ProductDetails pd : result.getProductDetailsList()) {
                    details.put(pd.getProductId(), pd);
                    List<ProductDetails.SubscriptionOfferDetails> subs = pd.getSubscriptionOfferDetails();
                    if (subs == null) continue;
                    for (ProductDetails.SubscriptionOfferDetails o : subs) offers.put(offerJson(o));
                }
                JSObject ret = new JSObject();
                ret.put("available", true);
                ret.put("offers", offers);
                call.resolve(ret);
            });
        });
    }

    private static JSObject offerJson(ProductDetails.SubscriptionOfferDetails o) {
        JSObject offer = new JSObject();
        offer.put("basePlanId", o.getBasePlanId());
        if (o.getOfferId() != null) offer.put("offerId", o.getOfferId());
        JSArray phases = new JSArray();
        for (ProductDetails.PricingPhase p : o.getPricingPhases().getPricingPhaseList()) {
            JSObject phase = new JSObject();
            phase.put("price", p.getFormattedPrice());
            phase.put("priceMicros", p.getPriceAmountMicros());
            phase.put("currency", p.getPriceCurrencyCode());
            phase.put("period", p.getBillingPeriod());
            phase.put("cycles", p.getBillingCycleCount());
            phases.put(phase);
        }
        offer.put("phases", phases);
        return offer;
    }

    // ── Purchase ───────────────────────────────────────────────────────

    @PluginMethod
    public void purchase(PluginCall call) {
        String id = call.getString("productId", productId);
        String basePlanId = call.getString("basePlanId", "");
        String offerId = call.getString("offerId");
        productId = id;
        withClient(setup -> {
            if (!isOk(setup)) {
                call.resolve(status("unavailable", false));
                return;
            }
            ProductDetails pd = details.get(id);
            String token = pd == null ? null : offerToken(pd, basePlanId, offerId);
            if (token == null) {
                call.resolve(status("error", false));
                return;
            }
            BillingFlowParams flow = BillingFlowParams.newBuilder()
                .setProductDetailsParamsList(Collections.singletonList(
                    BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(pd).setOfferToken(token).build()))
                .build();
            synchronized (this) {
                if (purchaseCall != null) {
                    call.resolve(status("error", false));
                    return;
                }
                purchaseCall = call;
            }
            getActivity().runOnUiThread(() -> {
                BillingResult r = client.launchBillingFlow(getActivity(), flow);
                if (!isOk(r)) finishPurchase(statusFor(r.getResponseCode(), false, false), false);
            });
        });
    }

    private static String offerToken(ProductDetails pd, String basePlanId, String offerId) {
        List<ProductDetails.SubscriptionOfferDetails> subs = pd.getSubscriptionOfferDetails();
        if (subs == null) return null;
        for (ProductDetails.SubscriptionOfferDetails o : subs) {
            if (o.getBasePlanId().equals(basePlanId) && Objects.equals(o.getOfferId(), offerId)) return o.getOfferToken();
        }
        return null;
    }

    @Override
    public void onPurchasesUpdated(BillingResult result, List<Purchase> purchases) {
        boolean active = false;
        boolean pending = false;
        if (isOk(result) && purchases != null) {
            for (Purchase p : purchases) {
                if (!p.getProducts().contains(productId)) continue;
                if (p.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                    active = true;
                    acknowledge(p);
                } else if (p.getPurchaseState() == Purchase.PurchaseState.PENDING) {
                    pending = true;
                }
            }
        }
        finishPurchase(statusFor(result.getResponseCode(), active, pending), active);
    }

    private void finishPurchase(String status, boolean active) {
        PluginCall call;
        synchronized (this) {
            call = purchaseCall;
            purchaseCall = null;
        }
        if (call != null) {
            call.resolve(status(status, active));
        } else if (active) {
            JSObject e = new JSObject();
            e.put("active", true);
            notifyListeners("entitlement", e);
        }
    }

    private static String statusFor(int code, boolean active, boolean pending) {
        switch (code) {
            case BillingClient.BillingResponseCode.OK:
                return active ? "purchased" : pending ? "pending" : "error";
            case BillingClient.BillingResponseCode.USER_CANCELED:
                return "canceled";
            case BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED:
                return "owned";
            case BillingClient.BillingResponseCode.BILLING_UNAVAILABLE:
            case BillingClient.BillingResponseCode.SERVICE_UNAVAILABLE:
            case BillingClient.BillingResponseCode.SERVICE_DISCONNECTED:
            case BillingClient.BillingResponseCode.NETWORK_ERROR:
                return "unavailable";
            default:
                return "error";
        }
    }

    private static JSObject status(String status, boolean active) {
        JSObject ret = new JSObject();
        ret.put("status", status);
        ret.put("active", active);
        return ret;
    }

    // ── Entitlement ────────────────────────────────────────────────────

    @PluginMethod
    public void getEntitlement(PluginCall call) {
        String id = call.getString("productId", productId);
        productId = id;
        withClient(setup -> {
            if (!isOk(setup)) {
                call.resolve(unavailable(setup));
                return;
            }
            QueryPurchasesParams params = QueryPurchasesParams.newBuilder().setProductType(BillingClient.ProductType.SUBS).build();
            client.queryPurchasesAsync(params, (r, purchases) -> {
                if (!isOk(r)) {
                    call.resolve(unavailable(r));
                    return;
                }
                boolean active = false;
                for (Purchase p : purchases) {
                    if (p.getProducts().contains(id) && p.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                        active = true;
                        acknowledge(p);
                    }
                }
                JSObject ret = new JSObject();
                ret.put("available", true);
                ret.put("active", active);
                call.resolve(ret);
            });
        });
    }

    /** Unacknowledged purchases are refunded by Play after three days */
    private void acknowledge(Purchase p) {
        if (p.isAcknowledged()) return;
        AcknowledgePurchaseParams params = AcknowledgePurchaseParams.newBuilder().setPurchaseToken(p.getPurchaseToken()).build();
        client.acknowledgePurchase(params, r -> {
            // Not acknowledged now: the next getEntitlement() tries again
        });
    }

    // ── Manage ─────────────────────────────────────────────────────────

    /** Opens the subscription in Google Play (cancel, change plan, payment method) */
    @PluginMethod
    public void manage(PluginCall call) {
        String id = call.getString("productId", productId);
        Uri uri = Uri.parse("https://play.google.com/store/account/subscriptions?sku=" + Uri.encode(id)
            + "&package=" + Uri.encode(getContext().getPackageName()));
        try {
            getActivity().startActivity(new Intent(Intent.ACTION_VIEW, uri));
            call.resolve();
        } catch (ActivityNotFoundException e) {
            call.reject("No app can open Google Play");
        }
    }
}
