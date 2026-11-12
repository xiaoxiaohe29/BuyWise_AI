
const API = "/shopping";
const USER_ID = "user001";
const ORDER_ID = 7;

async function fetchJSON(path) {
    const response = await fetch(`${API}${path}`);

    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }

    return response.json();
}

function showRows(elementId, rows) {
    const container = document.getElementById(elementId);
    container.replaceChildren();

    if (rows.length === 0) {
        container.textContent = "No records found.";
        return;
    }

    for (const [label, value] of rows) {
        const row = document.createElement("div");
        row.className = "data-row";

        const left = document.createElement("span");
        left.textContent = label;

        const right = document.createElement("strong");
        right.textContent = value;

        row.append(left, right);
        container.appendChild(row);
    }
}

function setupNavigation() {
    const buttons = document.querySelectorAll(".nav-btn");
    const pages = document.querySelectorAll(".page");

    buttons.forEach(button => {
        button.addEventListener("click", () => {
            const pageName = button.dataset.page;

            buttons.forEach(b => b.classList.remove("active"));
            pages.forEach(p => p.classList.remove("active"));

            button.classList.add("active");

            document.getElementById(
                `${pageName}-page`
            ).classList.add("active");

            document.getElementById("page-title").textContent =
                button.textContent.trim();
        });
    });
}

async function loadDashboard() {
    try {
        const summary = await fetchJSON(
            `/api/users/${USER_ID}/expenses/summary`
        );

        const usd = summary.currencies?.USD || {
            total_spending: 0,
            transaction_count: 0,
            spending_by_category: {}
        };

        document.getElementById("total-spending").textContent =
            `USD ${usd.total_spending}`;

        document.getElementById("transaction-count").textContent =
            usd.transaction_count;

        showRows(
            "categories",
            Object.entries(usd.spending_by_category)
        );

        const monthly = await fetchJSON(
            `/api/users/${USER_ID}/expenses/monthly`
        );

        showRows(
            "monthly",
            Object.entries(monthly.monthly_spending.USD || {})
        );


const orders = await fetchJSON("/api/orders");

const ordersContainer = document.getElementById("orders");
ordersContainer.replaceChildren();

const userOrders = orders.filter(o => o.user_id === USER_ID);

for (const order of userOrders) {
    const row = document.createElement("div");
    row.className = "data-row";

    const info = document.createElement("span");
    info.textContent =
        `Order #${order.order_id} — ${order.merchant_name}
         | ${order.currency} ${order.total_amount}
         | ${order.order_status}`;

    row.appendChild(info);

    if (order.order_status === "PENDING") {
        const payButton = document.createElement("button");
        payButton.textContent = "Pay with PayPal";
        payButton.className = "pay-btn";

        payButton.addEventListener("click", async () => {
            await startPayPalPayment(order.order_id);
        });

        row.appendChild(payButton);
    }

    ordersContainer.appendChild(row);
}

        const payments = await fetchJSON(
            `/api/users/${USER_ID}/payments`
        );

        showRows(
            "payments",
            payments.map(p => [
                `Order #${p.order_id}`,
                `${p.currency} ${p.amount} — ${p.payment_status}`
            ])
        );

        // Load delivery information only if an order exists
        if (orders.length > 0) {
            try {
                const delivery = await fetchJSON(
                    `/api/orders/${orders[0].order_id}/delivery`
                );

                showRows("delivery", [
                    ["Courier", delivery.courier],
                    ["Tracking Number", delivery.tracking_number],
                    ["Status", delivery.delivery_status]
                ]);
            } catch (error) {
                console.error("Delivery error:", error);
                document.getElementById("delivery").textContent =
                    "No delivery information available.";
            }
        } else {
            document.getElementById("delivery").textContent =
                "No orders yet.";
        }

    } catch (error) {
        console.error(error);
        alert("Unable to load dashboard. Check FastAPI server.");
    }
}

async function startPayPalPayment(orderId) {
    try {
        const response = await fetch(
            `${API}/api/orders/${orderId}/paypal`,
            { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Unable to create payment");
        }

        if (!data.approval_url) {
            throw new Error("PayPal approval URL not found");
        }

        // Save the order ID before redirecting to PayPal
        sessionStorage.setItem("pendingPayPalOrderId", String(orderId));

        // Redirect user to PayPal Sandbox
        window.location.href = data.approval_url;

    } catch (error) {
        alert(error.message);
    }
}

async function handlePayPalReturn() {
    const params = new URLSearchParams(window.location.search);
    const pendingId = sessionStorage.getItem("pendingPayPalOrderId");

    if (!pendingId) return;

    // PayPal cancellation
    if (params.has("cancel")) {
        sessionStorage.removeItem("pendingPayPalOrderId");
        window.history.replaceState({}, "", "/shopping/dashboard");
        alert("PayPal payment was cancelled.");
        return;
    }

    // Only capture after PayPal returns with an order token
    const token = params.get("token");

    if (!token) return;

    try {
        const response = await fetch(
            `${API}/api/orders/${pendingId}/capture`,
            { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Payment capture failed");
        }

        if (data.payment_status !== "COMPLETED" &&
            data.message !== "Payment already completed") {
            throw new Error("Payment completion not confirmed");
        }

        sessionStorage.removeItem("pendingPayPalOrderId");
        window.history.replaceState({}, "", "/dashboard");

        alert("Payment completed successfully.");
        window.location.reload();

    } catch (error) {
        alert(error.message);
    }
}

async function initializeDashboard() {
    setupNavigation();

    // Wait for PayPal return processing to finish
    await handlePayPalReturn();

    // Then load the latest order and payment statuses
    await loadDashboard();
}

initializeDashboard();
