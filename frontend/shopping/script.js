
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
        button.addEventListener("click", async () => {
            const pageName = button.dataset.page;

            buttons.forEach(b => b.classList.remove("active"));
            pages.forEach(p => p.classList.remove("active"));

            button.classList.add("active");

            const selectedPage = document.getElementById(
                `${pageName}-page`
            );

            if (selectedPage) {
                selectedPage.classList.add("active");
            }

            document.getElementById("page-title").textContent =
                button.textContent.trim();

            if (pageName === "dashboard") {
                await loadDashboard();
            } else if (pageName === "orders") {
                await loadOrders();
            } else if (pageName === "payments") {
                await loadPayments();
            } else if (pageName === "delivery") {
                await loadDelivery();
            }
        });
    });
}




async function loadDashboard() {
    try {
        // ==========================================
        // 1. FETCH USD SUMMARY
        // ==========================================

        const usdSummary = await fetchJSON(
            `/api/users/${USER_ID}/expenses/summary-usd`
        );

        document.getElementById("total-spending").textContent =
            `USD ${Number(usdSummary.total_spending || 0).toFixed(2)}`;

        document.getElementById("transaction-count").textContent =
            usdSummary.transaction_count || 0;


        // ==========================================
        // 2. MONTH FILTER
        // ==========================================

        const selectedMonth =
            document.getElementById("category-month")?.value || "";

        const monthQuery = selectedMonth
            ? `?month=${encodeURIComponent(selectedMonth)}`
            : "";


        // ==========================================
        // 3. FETCH CATEGORY SPENDING
        // ==========================================

        const categorySummary = await fetchJSON(
            `/api/users/${USER_ID}/expenses/categories-usd${monthQuery}`
        );

        const categoryData =
            categorySummary.spending_by_category || {};


        // ==========================================
        // 4. DISPLAY CATEGORY RECORDS
        // ==========================================

        showRows(
            "categories",
            Object.entries(categoryData).map(
                ([category, amount]) => [
                    category,
                    `USD ${Number(amount).toFixed(2)}`
                ]
            )
        );


        // ==========================================
        // 5. PREPARE PIE CHART DATA
        // ==========================================

        const chartCanvas =
            document.getElementById("categoryPieChart");

        if (chartCanvas && typeof Chart !== "undefined") {

            const sortedCategories = Object.entries(categoryData)
                .map(([category, amount]) => ({
                    category,
                    amount: Number(amount)
                }))
                .filter(item =>
                    Number.isFinite(item.amount) && item.amount > 0
                )
                .sort((a, b) => b.amount - a.amount);

            // Display Top 5 categories
            const topCategories = sortedCategories.slice(0, 5);

            // Combine remaining categories into Others
            const remainingCategories = sortedCategories.slice(5);

            const othersTotal = remainingCategories.reduce(
                (total, item) => total + item.amount,
                0
            );

            const labels =
                topCategories.map(item => item.category);

            const values =
                topCategories.map(item => item.amount);

            if (othersTotal > 0) {
                labels.push("Others");
                values.push(othersTotal);
            }


            // ==========================================
            // 6. DESTROY PREVIOUS CHART
            // ==========================================

            const existingChart = Chart.getChart(chartCanvas);

            if (existingChart) {
                existingChart.destroy();
            }


            // ==========================================
            // 7. CREATE PIE CHART
            // ==========================================

            if (values.some(value => value > 0)) {

                new Chart(chartCanvas, {
                    type: "pie",

                    data: {
                        labels: labels,

                        datasets: [{
                            label: "Spending (USD)",
                            data: values,

                            backgroundColor: [
                                "#6366f1",
                                "#22c55e",
                                "#f59e0b",
                                "#ef4444",
                                "#06b6d4",
                                "#a855f7",
                                "#ec4899"
                            ],

                            borderColor: "#eee9f7",
                            borderWidth: 2,
                            hoverOffset: 8
                        }]
                    },

                    options: {
                        responsive: true,
                        maintainAspectRatio: false,

                        layout: {
                            padding: {
                                top: 20,
                                bottom: 15,
                                left: 15,
                                right: 15
                            }
                        },

                        plugins: {
                            legend: {
                                display: true,
                                position: "bottom",
                                align: "center",

                                labels: {
                                    color: "#392765",

                                    font: {
                                        family: "Arial",
                                        size: 13,
                                        weight: "600"
                                    },

                                    padding: 18,
                                    boxWidth: 14,
                                    boxHeight: 14,
                                    usePointStyle: true,
                                    pointStyle: "circle"
                                }
                            },

                            tooltip: {
                                backgroundColor: "#392765",
                                titleColor: "#ffffff",
                                bodyColor: "#ffffff",
                                padding: 12,
                                cornerRadius: 10,

                                callbacks: {
                                    label: function(context) {
                                        const value =
                                            Number(context.parsed || 0);

                                        return `${context.label}: USD ${value.toFixed(2)}`;
                                    }
                                }
                            }
                        }
                    }
                });

            } else {
                // No spending data
                const ctx = chartCanvas.getContext("2d");

                if (ctx) {
                    ctx.clearRect(
                        0,
                        0,
                        chartCanvas.width,
                        chartCanvas.height
                    );
                }
            }
        }


        // ==========================================
        // 8. FETCH MONTHLY SPENDING
        // ==========================================

        const monthly = await fetchJSON(
            `/api/users/${USER_ID}/expenses/monthly-usd`
        );


        // ==========================================
        // 9. DISPLAY MONTHLY RECORDS
        // ==========================================

        showRows(
            "monthly",
            Object.entries(monthly.monthly_spending || {}).map(
                ([month, amount]) => [
                    month,
                    `USD ${Number(amount).toFixed(2)}`
                ]
            )
        );

    } catch (error) {
        console.error("Dashboard loading error:", error);
    }
}


/* ==========================================
   ORDERS, PAYMENTS AND DELIVERY
   ========================================== */

async function loadOrders() {
    const container = document.getElementById("orders");
    if (!container) return;

    container.textContent = "Loading orders...";

    try {
        const orders = await fetchJSON("/api/orders");

        // Show only the current user's orders
        const userOrders = orders.filter(
            order => order.user_id === USER_ID
        );

        userOrders.sort(
            (a, b) => Number(b.order_id) - Number(a.order_id)
        );

        if (userOrders.length === 0) {
            container.textContent = "No orders found.";
            return;
        }

        container.replaceChildren();

        for (const order of userOrders) {
            const card = document.createElement("div");
            card.className = "data-row";

            const details = document.createElement("div");

            const title = document.createElement("strong");
            title.textContent =
                `Order #${order.order_id} — ${order.merchant_name}`;

            const info = document.createElement("p");
            info.textContent =
                `${order.platform} | ${order.currency} ` +
                `${Number(order.total_amount).toFixed(2)} | ` +
                `${order.order_status}`;

            details.append(title, info);

            if (Array.isArray(order.items)) {
                for (const item of order.items) {
                    const product = document.createElement("p");
                    product.textContent =
                        `${item.product_name} × ${item.quantity}`;
                    details.appendChild(product);
                }
            }

            card.appendChild(details);

            if (order.order_status === "PENDING") {
                const payButton = document.createElement("button");
                payButton.type = "button";
                payButton.textContent = "Pay with PayPal";

                payButton.addEventListener("click", async () => {
                    payButton.disabled = true;
                    try {
                        await startPayPalPayment(order.order_id);
                    } finally {
                        payButton.disabled = false;
                    }
                });

                card.appendChild(payButton);
            }

            container.appendChild(card);
        }

    } catch (error) {
        console.error("Orders loading error:", error);
        container.textContent =
            `Unable to load orders: ${error.message}`;
    }
}


async function loadPayments() {
    const container = document.getElementById("payments");
    if (!container) return;

    container.textContent = "Loading payments...";

    try {
        const payments = await fetchJSON(
            `/api/users/${USER_ID}/payments`
        );

        if (payments.length === 0) {
            container.textContent = "No payment records found.";
            return;
        }

        showRows(
            "payments",
            payments.map(payment => [
                `Payment #${payment.payment_id} | Order #${payment.order_id}`,
                `${payment.currency} ` +
                `${Number(payment.amount).toFixed(2)} — ` +
                `${payment.payment_status}`
            ])
        );

    } catch (error) {
        console.error("Payments loading error:", error);
        container.textContent =
            `Unable to load payments: ${error.message}`;
    }
}


/* ==========================================
   DELIVERY TRACKING DASHBOARD
   ========================================== */

let allDeliveries = [];

// Convert backend status into a consistent format
function normalizeDeliveryStatus(status) {
    const value = String(status || "NOT_SHIPPED")
        .trim()
        .toUpperCase()
        .replace(/[\s-]+/g, "_");

    if (value === "SHIPPED") return "IN_TRANSIT";
    if (value === "OUT_FOR_DELIVERY") return "IN_TRANSIT";

    return value;
}

function deliveryStatusLabel(status) {
    return status.replace(/_/g, " ");
}

// Create text elements safely
function parcelElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

// Create a single parcel card
function createParcelCard(delivery) {
    const status = normalizeDeliveryStatus(
        delivery.delivery_status
    );

    const card = parcelElement("article", "parcel-card");

    // Header
    const header = parcelElement("div", "parcel-header");

    header.appendChild(
        parcelElement(
            "span",
            "parcel-order-id",
            `📦 Order #${delivery.order_id}`
        )
    );

    const badge = parcelElement(
        "span",
        "parcel-status",
        deliveryStatusLabel(status)
    );

    if (status === "DELIVERED") {
        badge.classList.add("delivered");
    } else if (status === "IN_TRANSIT") {
        badge.classList.add("in-transit");
    }

    header.appendChild(badge);
    card.appendChild(header);

    // Courier and tracking information
    const info = parcelElement("div", "parcel-info");

    const fields = [
        [
            "Courier",
            delivery.courier || "Not assigned"
        ],
        [
            "Tracking Number",
            delivery.tracking_number || "Not available"
        ]
    ];

    fields.forEach(([label, value]) => {
        const field = parcelElement("div");

        field.appendChild(
            parcelElement("div", "parcel-info-label", label)
        );

        field.appendChild(
            parcelElement("div", "parcel-info-value", value)
        );

        info.appendChild(field);
    });

    card.appendChild(info);

    // Tracking timeline
    const timeline = parcelElement(
        "div",
        "parcel-timeline"
    );

    const steps = [
        ["📋", "Placed"],
        ["📦", "Packed"],
        ["🚚", "Shipped"],
        ["🏠", "Delivered"]
    ];

    // Conservative progress based on known delivery status
    const progress = {
        NOT_SHIPPED: 0,
        PACKED: 1,
        READY_TO_SHIP: 1,
        IN_TRANSIT: 2,
        DELIVERED: 3
    };

    const currentStep = progress[status] ?? -1;

    steps.forEach(([icon, label], index) => {
        const step = parcelElement("div", "parcel-step");

        if (index <= currentStep) {
            step.classList.add("active");
        }

        step.appendChild(
            parcelElement("div", "parcel-step-icon", icon)
        );

        step.appendChild(
            parcelElement("div", "", label)
        );

        timeline.appendChild(step);
    });

    card.appendChild(timeline);

    // Status message
    const messages = {
        NOT_SHIPPED:
            "Waiting for shipment. Tracking information will appear once the seller ships the parcel.",
        PACKED:
            "The parcel is marked as packed and is waiting for shipment.",
        READY_TO_SHIP:
            "The parcel is ready to be shipped.",
        IN_TRANSIT:
            "The parcel is marked as shipped or in transit. Check the courier for the latest updates.",
        DELIVERED:
            "The parcel is marked as delivered."
    };

    card.appendChild(
        parcelElement(
            "div",
            "parcel-message",
            messages[status] ||
            `Current delivery status: ${deliveryStatusLabel(status)}`
        )
    );

    // Expandable parcel details
    const details = parcelElement(
        "details",
        "parcel-details"
    );

    const summary = parcelElement(
        "summary",
        "",
        "View Parcel Details"
    );

    details.appendChild(summary);

    const content = parcelElement(
        "div",
        "parcel-details-content"
    );

    content.appendChild(
        parcelElement(
            "p",
            "",
            `Order ID: ${delivery.order_id}`
        )
    );

    content.appendChild(
        parcelElement(
            "p",
            "",
            `Delivery Status: ${deliveryStatusLabel(status)}`
        )
    );

    content.appendChild(
        parcelElement(
            "p",
            "",
            `Courier: ${delivery.courier || "Not assigned"}`
        )
    );

    content.appendChild(
        parcelElement(
            "p",
            "",
            `Tracking Number: ${
                delivery.tracking_number || "Not available"
            }`
        )
    );

    // Copy tracking number when available
    if (delivery.tracking_number) {
        const copyButton = parcelElement(
            "button",
            "parcel-copy-btn",
            "📋 Copy Tracking Number"
        );

        copyButton.type = "button";

        copyButton.addEventListener("click", async () => {
            try {
                await navigator.clipboard.writeText(
                    delivery.tracking_number
                );

                copyButton.textContent = "✓ Copied!";
            } catch (error) {
                console.error("Copy failed:", error);
                copyButton.textContent = "Unable to copy";
            }
        });

        content.appendChild(copyButton);
    }

    details.appendChild(content);
    card.appendChild(details);

    return card;
}

// Display parcels using search and filter
function renderDeliveries() {
    const container = document.getElementById("delivery");
    if (!container) return;

    const search = (
        document.getElementById("delivery-search")?.value || ""
    ).trim().toLowerCase();

    const filter = (
        document.getElementById("delivery-filter")?.value || "ALL"
    );

    const filtered = allDeliveries.filter(delivery => {
        const status = normalizeDeliveryStatus(
            delivery.delivery_status
        );

        const searchableText = [
            delivery.order_id,
            delivery.tracking_number,
            delivery.courier
        ].join(" ").toLowerCase();

        const matchesSearch = searchableText.includes(search);

        const matchesFilter =
            filter === "ALL" || status === filter;

        return matchesSearch && matchesFilter;
    });

    container.replaceChildren();

    if (filtered.length === 0) {
        container.appendChild(
            parcelElement(
                "div",
                "parcel-empty",
                "No matching parcels found."
            )
        );
        return;
    }

    filtered.forEach(delivery => {
        container.appendChild(createParcelCard(delivery));
    });
}

// Update parcel summary statistics
function updateDeliveryStats() {
    const total = allDeliveries.length;

    const transit = allDeliveries.filter(delivery =>
        normalizeDeliveryStatus(
            delivery.delivery_status
        ) === "IN_TRANSIT"
    ).length;

    const delivered = allDeliveries.filter(delivery =>
        normalizeDeliveryStatus(
            delivery.delivery_status
        ) === "DELIVERED"
    ).length;

    document.getElementById("delivery-total").textContent =
        total;

    document.getElementById("delivery-transit").textContent =
        transit;

    document.getElementById("delivery-delivered").textContent =
        delivered;
}

// Main loading function
async function loadDelivery() {
    const container = document.getElementById("delivery");
    if (!container) return;

    container.textContent = "Loading deliveries...";

    // Attach search/filter events once
    const searchInput = document.getElementById(
        "delivery-search"
    );

    const filterSelect = document.getElementById(
        "delivery-filter"
    );

    if (searchInput && !searchInput.dataset.initialized) {
        searchInput.addEventListener("input", renderDeliveries);
        searchInput.dataset.initialized = "true";
    }

    if (filterSelect && !filterSelect.dataset.initialized) {
        filterSelect.addEventListener(
            "change",
            renderDeliveries
        );
        filterSelect.dataset.initialized = "true";
    }

    try {
        const orders = await fetchJSON("/api/orders");

        const userOrders = orders.filter(
            order =>
                order.user_id === USER_ID &&
                order.order_status === "COMPLETED"
        );

        // Use the same API base as your existing app
        const apiBase =
            typeof API !== "undefined" ? API : "/shopping";

        const results = await Promise.all(
            userOrders.map(async order => {
                const response = await fetch(
                    `${apiBase}/api/orders/${order.order_id}/delivery`
                );

                if (response.status === 404) return null;

                if (!response.ok) {
                    throw new Error(
                        `Delivery request failed: ${response.status}`
                    );
                }

                return response.json();
            })
        );

        allDeliveries = results.filter(Boolean);

        // Show newest order first
        allDeliveries.sort(
            (a, b) =>
                Number(b.order_id) - Number(a.order_id)
        );

        updateDeliveryStats();
        renderDeliveries();

    } catch (error) {
        console.error("Delivery loading error:", error);
        container.textContent =
            `Unable to load deliveries: ${error.message}`;
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

        // Save BuyWise AI Order ID
        sessionStorage.setItem("pendingPayPalOrderId", String(orderId));

        // Save PayPal Order ID
        sessionStorage.setItem("pendingPayPalToken", data.paypal_order_id);

        // Redirect to PayPal Sandbox
        window.location.href = data.approval_url;

    } catch (error) {
        alert(error.message);
    }
}


async function handlePayPalReturn() {
    const params = new URLSearchParams(window.location.search);
    const pendingId = sessionStorage.getItem("pendingPayPalOrderId");

    if (!pendingId) return;

    // Handle PayPal cancellation
    if (params.has("cancel")) {
        sessionStorage.removeItem("pendingPayPalOrderId");
        sessionStorage.removeItem("pendingPayPalToken");

        window.history.replaceState({}, "", "/shopping/dashboard");
        alert("PayPal payment was cancelled.");
        return;
    }

    // Get PayPal token from return URL
    const token = params.get("token");

    if (!token) return;

    // Verify the saved PayPal token
    const expectedToken = sessionStorage.getItem("pendingPayPalToken");

    if (!expectedToken || token !== expectedToken) {
        alert("PayPal order verification failed. Payment was not captured.");
        return;
    }

    try {
        // Automatically capture PayPal payment
        const response = await fetch(
            `${API}/api/orders/${pendingId}/capture`,
            { method: "POST" }
        );

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Payment capture failed");
        }

        if (
            data.payment_status !== "COMPLETED" &&
            data.message !== "Payment already completed"
        ) {
            throw new Error("Payment completion not confirmed");
        }

        // Clear saved PayPal information
        sessionStorage.removeItem("pendingPayPalOrderId");
        sessionStorage.removeItem("pendingPayPalToken");

        // Remove PayPal token from URL
        window.history.replaceState({}, "", "/shopping/dashboard");

        alert("Payment completed successfully.");
        window.location.reload();

    } catch (error) {
        alert(error.message);
    }
}


function setupCreateOrder() {
    const addButton = document.getElementById("add-order-btn");
    const cancelButton = document.getElementById("cancel-order-btn");
    const formContainer = document.getElementById("order-form-container");
    const form = document.getElementById("create-order-form");
    const saveButton = document.getElementById("save-order-btn");
    const message = document.getElementById("order-form-message");

    // Show the form
    addButton.addEventListener("click", () => {
        formContainer.hidden = false;
        message.textContent = "";
        addButton.hidden = true;
    });

    // Close the form
    cancelButton.addEventListener("click", () => {
        formContainer.hidden = true;
        addButton.hidden = false;
        form.reset();
        message.textContent = "";
    });

    // Submit the new order
    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!form.reportValidity()) {
            return;
        }

        const quantity = Number(
            document.getElementById("product-quantity").value
        );

        const price = Number(
            document.getElementById("product-price").value
        );

        if (!Number.isInteger(quantity) || quantity < 1 ||
            !Number.isFinite(price) || price <= 0) {
            message.textContent = "Please enter a valid quantity and price.";
            return;
        }

        const orderData = {
            user_id: USER_ID,
            merchant_name: document.getElementById("merchant-name").value.trim(),
            platform: document.getElementById("order-platform").value,
            currency: document.getElementById("order-currency").value,
            items: [
                {
                    product_name: document.getElementById("product-name").value.trim(),
                    quantity: quantity,
                    unit_price: price.toFixed(2),
                    category: document.getElementById("product-category").value
                }
            ]
        };

        saveButton.disabled = true;
        message.textContent = "Creating order...";

        try {
            const response = await fetch(`${API}/api/orders`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(orderData)
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(
                    typeof result.detail === "string"
                        ? result.detail
                        : JSON.stringify(result.detail || "Unable to create order")
                );
            }

            message.textContent = `Order #${result.order_id} created successfully!`;

            form.reset();
            formContainer.hidden = true;
            addButton.hidden = false;

            await loadOrders();
            await loadDashboard();

        } catch (error) {
            message.textContent = `Error: ${error.message}`;
        } finally {
            saveButton.disabled = false;
        }
    });
}


function setupCategoryMonthFilter() {
    const monthInput = document.getElementById("category-month");
    const resetButton = document.getElementById("reset-category-month");

    // Get current year and month
    const today = new Date();
    const currentYear = today.getFullYear();
    const currentMonth = String(today.getMonth() + 1).padStart(2, "0");

    // Disable future months
    monthInput.max = `${currentYear}-${currentMonth}`;

    monthInput.addEventListener("change", async () => {
        if (monthInput.value > monthInput.max) {
            monthInput.value = monthInput.max;
        }

        await loadDashboard();
    });

    resetButton.addEventListener("click", async () => {
        monthInput.value = "";
        await loadDashboard();
    });
}


async function initializeDashboard() {
    setupNavigation();
    setupQuickAccess();
    setupCreateOrder();
    setupCategoryMonthFilter();

    await handlePayPalReturn();
    await loadDashboard();
}

initializeDashboard();


 // Site-wide Momo helper
function setupMomo() {
    const toggle = document.getElementById('bw-momo-toggle');
    const panel = document.getElementById('bw-momo-panel');
    const message = document.getElementById('bw-momo-message');
    const next = document.getElementById('bw-momo-next');
    const tour = document.getElementById('bw-momo-tour');
    const navigate = document.getElementById('bw-momo-nav');
    const close = document.getElementById('bw-momo-close');

    if (!toggle || !panel) return;

    const tips = {
        dashboard: [
            'Welcome to BuyWise AI! This dashboard summarizes your spending and transactions.',
            'Use the month filter to inspect spending by category.'
        ],
        orders: [
            'Orders shows your purchase history.',
            'Select + Order to record a new purchase.'
        ],
        payments: [
            'Payments displays payment records and their status.',
            'For pending orders, use Pay with PayPal in Orders.'
        ],
        delivery: [
            'Delivery shows shipment status, courier, and tracking information.'
        ],
        merchant: [
            'Seller Credibility helps you explore seller review signals.',
            'The sample seller profiles are demonstrations, not live verified assessments.'
        ],
        coupon: [
            'Coupon & Bundle Advisor compares example voucher and bundle scenarios.',
            'Check real platform terms before relying on estimated savings.'
        ]
    };

    let tipIndex = 0;

    const currentPage = () =>
        document.querySelector('.nav-btn.active')?.dataset.page || 'dashboard';

    function render() {
        const page = currentPage();
        const messages = tips[page] || tips.dashboard;

        message.textContent = messages[tipIndex % messages.length];

       tour.hidden = !['dashboard', 'orders', 'payments','delivery', 'merchant', 'coupon'].includes(page);
        navigate.hidden = page === 'coupon';

        navigate.textContent =
            page === 'merchant' ? 'Open Coupon Advisor' : 'Seller Credibility';
    }

    function openPanel() {
        panel.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        tipIndex = 0;
        render();
    }

    function closePanel() {
        panel.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
    }

    toggle.addEventListener('click', () => {
        panel.hidden ? openPanel() : closePanel();
    });

    close.addEventListener('click', closePanel);

    next.addEventListener('click', () => {
        tipIndex++;
        render();
    });

    document.querySelectorAll('.nav-btn').forEach(button => {
        button.addEventListener('click', () => {
            tipIndex = 0;
            if (!panel.hidden) render();
        });
    });

    navigate.addEventListener('click', () => {
        const target =
            currentPage() === 'merchant' ? 'coupon' : 'merchant';

        document.querySelector(
            `.nav-btn[data-page="${target}"]`
        )?.click();

        render();
    });
   
    tour.addEventListener('click', () => {
        const activePage = document.querySelector('.page.active');
        const page = activePage
            ? activePage.id.replace('-page', '')
            : 'dashboard';
            console.log("Momo current page:", page);

        if (['dashboard', 'orders', 'payments', 'delivery'].includes(page)) {
            closePanel();
            startDashboardMomoTour(page);
            return;
        }

        // Existing React guided tours
        if (page !== 'merchant' && page !== 'coupon') {
            return;
        }

        const iframe = document.querySelector(
            page === 'merchant'
                ? '#merchant-page iframe'
                : '#coupon-page iframe'
        );

        const messageType = page === 'merchant'
            ? 'BUYWISE_START_SELLER_TOUR'
            : 'BUYWISE_START_COUPON_TOUR';

        iframe?.contentWindow?.postMessage(
            { type: messageType },
            window.location.origin
        );

        closePanel();
    });
}

setupMomo();


/* ==========================================
   BUYWISE AI - DASHBOARD MOMO GUIDED TOUR
   ========================================== */


const DASHBOARD_MOMO_STEPS = [
    {
        selector: "#dashboard-page .cards",
        title: "Welcome to BuyWise AI! 🐑",
        description:
            "Hello! I'm Momo, your shopping assistant. " +
            "Let me introduce your shopping dashboard!"
    },
    {
        selector: "#total-spending",
        title: "Total Spending 💰",
        description:
            "This card displays your total spending in USD."
    },
    {
        selector: "#transaction-count",
        title: "Your Transactions 🛍️",
        description:
            "Here you can see how many transactions " +
            "have been recorded in your account."
    },
    {
        selector: "#dashboard-page .quick-access-panel",
        title: "Quick Access 🚀",
        description:
            "These shortcuts help you quickly navigate to " +
            "Orders, Payments, Delivery, Seller Credibility, " +
            "and Coupon & Bundle Advisor."
    },
    {
        selector: "#dashboard-page .chart-filter",
        title: "Month Filter 📅",
        description:
            "Select a month to filter your category spending. " +
            "Choose All Time to view spending across all months."
    },
    {
        selector: "#dashboard-page .chart-container",
        title: "Spending by Category 📊",
        description:
            "This pie chart shows how your spending " +
            "is distributed across different shopping categories."
    },
    {
        selector: "#monthly",
        title: "Monthly Spending ✨",
        description:
            "Review your spending records for different months. " +
            "You're ready to explore BuyWise AI!"
    }
];


const DELIVERY_MOMO_STEPS = [
    {
        selector: "#delivery-page .delivery-heading",
        title: "Delivery Tracking 📦",
        description:
            "Welcome to Delivery Tracking! Here you can " +
            "monitor your orders and parcel journeys."
    },
    {
        selector: "#delivery-page .delivery-stats",
        title: "Parcel Overview 📊",
        description:
            "These cards display your total parcels, " +
            "parcels in transit, and delivered parcels."
    },
    {
        selector: "#delivery-search",
        title: "Search Parcels 🔎",
        description:
            "Search for a specific parcel using its " +
            "order number or tracking number."
    },
    {
        selector: "#delivery-filter",
        title: "Filter Deliveries 📋",
        description:
            "Filter parcels by their delivery status " +
            "to find the information you need."
    },
    {
        selector: "#delivery-page .parcel-card .parcel-info",
        title: "Courier & Tracking 🚚",
        description:
            "This section displays the courier and " +
            "tracking number when they are available."
    },
    {
        selector: "#delivery-page .parcel-card .parcel-timeline",
        title: "Delivery Progress 🛣️",
        description:
            "Follow the parcel's progress from " +
            "order placement to delivery. " +
            "Progress is based on the recorded delivery status."
    },
    {
        selector: "#delivery-page .parcel-card .parcel-details",
        title: "Parcel Details ✨",
        description:
            "Click View Parcel Details to expand " +
            "the parcel's delivery information."
    }
];


const PAYMENTS_MOMO_STEPS = [
    {
        selector: "#payments-page .panel",
        title: "Payment History 💳",
        description:
            "Hello! I'm Momo! Here you can view your " +
            "payment history, check transaction amounts, " +
            "and track payment statuses."
    }
];

const ORDERS_MOMO_STEPS = [
    {
        selector: "#orders-page .orders-header",
        title: "Welcome to Orders! 🛒",
        description:
            "I'm Momo! Here you can manage your purchases, " +
            "check your order history, and create new orders."
    },
    {
        selector: "#add-order-btn",
        title: "Create a New Order ✨",
        description:
            "Click the + Order button to create a new order. " +
            "Let's explore the order form together!",
        beforeShow: () => {
            const form = document.getElementById("order-form-container");

            if (form && getComputedStyle(form).display === "none") {
                document.getElementById("add-order-btn")?.click();
            }
        }
    },
    {
        selector: "#create-order-form",
        title: "Enter Your Order Details 📝",
        description:
            "Fill in the merchant, platform, currency, " +
            "product name, category, quantity, and price. " +
            "Make sure the information is correct before " +
            "clicking Create Order."
    },
    {
        selector: "#orders",
        title: "Check Your Order ✅",
        description:
            "Here you can review your order records. " +
            "Check the merchant name, product details, " +
            "amount, and order status to make sure " +
            "everything is correct.",
        beforeShow: () => {
            document.getElementById("cancel-order-btn")?.click();
        }
    }
];



let dashboardMomoTour = null;


function startDashboardMomoTour(page = "dashboard") {
    const stepsByPage = {
        dashboard: DASHBOARD_MOMO_STEPS,
        orders: ORDERS_MOMO_STEPS,
        payments: PAYMENTS_MOMO_STEPS,
        delivery: DELIVERY_MOMO_STEPS
    };

    const steps = (
        stepsByPage[page] || DASHBOARD_MOMO_STEPS
    ).filter(step => document.querySelector(step.selector));

    if (dashboardMomoTour) {
        dashboardMomoTour.close();
    }

    let stepIndex = 0;
    let typingTimer = null;
    let moveTimer = null;
    let frameId = null;
    let highlightedElement = null;
    let closed = false;
    let fullText = "";
    let typedChars = 0;

    
    // Main tour overlay
    const overlay = document.createElement("div");
    overlay.className = "bw-tour-overlay";

    // Transparent backdrop for click-to-close
    const backdrop = document.createElement("div");
    backdrop.className = "bw-tour-backdrop";

    // Spotlight highlights the selected UI section
    const spotlight = document.createElement("div");
    spotlight.className = "bw-tour-spotlight";

    // Momo dialogue card
    const speech = document.createElement("div");
    speech.className = "bw-tour-speech";


    speech.innerHTML = `
        <div class="bw-tour-mascot">
            <img src="/shopping/frontend/momo.png?v=3"
                 alt="Momo the sheep">
        </div>

        <div class="bw-tour-header">
            <span id="bw-tour-progress">🐑 MOMO SAYS</span>
            <button id="bw-tour-close"
                    type="button"
                    aria-label="Close tour">×</button>
        </div>

        <h3 id="bw-tour-title"></h3>
        <p id="bw-tour-description"></p>

        <div class="bw-tour-controls">
            <button id="bw-tour-back" type="button">
                ← Back
            </button>
            <button id="bw-tour-next" type="button">
                Continue →
            </button>
        </div>
    `;

    overlay.append(backdrop, spotlight, speech);
    document.body.appendChild(overlay);

    const progress = speech.querySelector("#bw-tour-progress");
    const title = speech.querySelector("#bw-tour-title");
    const description = speech.querySelector("#bw-tour-description");
    const backButton = speech.querySelector("#bw-tour-back");
    const nextButton = speech.querySelector("#bw-tour-next");
    const closeButton = speech.querySelector("#bw-tour-close");

    function clearTimers() {
        clearInterval(typingTimer);
        clearTimeout(moveTimer);
        cancelAnimationFrame(frameId);

        typingTimer = null;
        moveTimer = null;
        frameId = null;
    }

    function removeHighlight() {
        if (highlightedElement) {
            highlightedElement.classList.remove("bw-tour-highlight");
            highlightedElement = null;
        }
    }

    function closeTour() {
        if (closed) return;

        closed = true;
        clearTimers();
        removeHighlight();

        window.removeEventListener("resize", schedulePosition);
        window.removeEventListener("scroll", schedulePosition, true);
        document.removeEventListener("keydown", handleKeydown);

        overlay.remove();
        dashboardMomoTour = null;
    }

    function schedulePosition() {
        if (closed || frameId !== null) return;

        frameId = requestAnimationFrame(() => {
            frameId = null;
            positionSpeech();
        });
    }


function positionSpeech() {
    if (closed) return;

    const step = steps[stepIndex];
    if (!step) return;

    const target = document.querySelector(step.selector);

    const margin = 16;
    const gap = 24;
    const mascotSpace = 20;

    const vw = window.innerWidth;
    const vh = window.innerHeight;

    // Reset before measuring
    speech.style.transform = "none";
    speech.style.left = "0px";
    speech.style.top = "0px";

    const cardWidth = speech.offsetWidth;
    const cardHeight = speech.offsetHeight;

    spotlight.style.display = "none";

    // Keep the dialogue fully visible
    const clamp = (value, min, max) =>
        Math.max(min, Math.min(value, max));

    const maxLeft = Math.max(margin, vw - cardWidth - margin);
    const maxTop = Math.max(
        margin + mascotSpace,
        vh - cardHeight - margin
    );

    function placeCard(left, top) {
        speech.style.left =
            `${clamp(left, margin, maxLeft)}px`;

        speech.style.top =
            `${clamp(top, margin + mascotSpace, maxTop)}px`;
    }

    // Fallback if the highlighted element is unavailable
    if (!target || target.getClientRects().length === 0) {
        placeCard(
            (vw - cardWidth) / 2,
            (vh - cardHeight) / 2
        );
        return;
    }

    const rect = target.getBoundingClientRect();
    const padding = 8;

    // Universal spotlight
    spotlight.style.display = "block";
    spotlight.style.left = `${rect.left - padding}px`;
    spotlight.style.top = `${rect.top - padding}px`;
    spotlight.style.width = `${rect.width + padding * 2}px`;
    spotlight.style.height = `${rect.height + padding * 2}px`;

    // Four possible positions
    const candidates = [
        {
            name: "right",
            left: rect.right + gap,
            top: rect.top
        },
        {
            name: "left",
            left: rect.left - cardWidth - gap,
            top: rect.top
        },
        {
            name: "bottom",
            left: rect.left + (rect.width - cardWidth) / 2,
            top: rect.bottom + gap
        },
        {
            name: "top",
            left: rect.left + (rect.width - cardWidth) / 2,
            top: rect.top - cardHeight - gap
        }
    ];

    const evaluated = candidates.map(candidate => {
        const left = clamp(
            candidate.left,
            margin,
            maxLeft
        );

        const top = clamp(
            candidate.top,
            margin + mascotSpace,
            maxTop
        );

        // Calculate overlap with highlighted section
        const overlapWidth = Math.max(
            0,
            Math.min(left + cardWidth, rect.right + padding) -
            Math.max(left, rect.left - padding)
        );

        const overlapHeight = Math.max(
            0,
            Math.min(top + cardHeight, rect.bottom + padding) -
            Math.max(top, rect.top - padding)
        );

        const overlap = overlapWidth * overlapHeight;

        // Penalize moving too far from intended position
        const displacement =
            Math.abs(left - candidate.left) +
            Math.abs(top - candidate.top);

        return {
            ...candidate,
            left,
            top,
            overlap,
            score: overlap * 100 + displacement
        };
    });

    // Prefer positions that do not overlap the highlight
    evaluated.sort((a, b) => a.score - b.score);

    const best = evaluated[0];

    placeCard(best.left, best.top);
}


    function updateNextButton() {
        nextButton.textContent =
            stepIndex === steps.length - 1
                ? "Finish ✓"
                : "Continue →";
    }

    function startTyping(text) {
        clearInterval(typingTimer);

        fullText = text;
        typedChars = 0;
        description.textContent = "";
        nextButton.textContent = "Skip typing »";

        typingTimer = setInterval(() => {
            typedChars = Math.min(typedChars + 2, fullText.length);
            description.textContent = fullText.slice(0, typedChars);

            if (typedChars >= fullText.length) {
                clearInterval(typingTimer);
                typingTimer = null;
                updateNextButton();
            }
        }, 25);
    }

    function showStep(index) {
        if (closed) return;

        if (index < 0 || index >= steps.length) {
            closeTour();
            return;
        }

        clearTimers();
        removeHighlight();

        stepIndex = index;
        const step = steps[stepIndex];

        if (typeof step.beforeShow === "function") {
            step.beforeShow();
        }

        progress.textContent =
            `🐑 MOMO SAYS · ${stepIndex + 1}/${steps.length}`;

        title.textContent = step.title;
        description.textContent = "";
        backButton.disabled = stepIndex === 0;

        const target = document.querySelector(step.selector);

        if (target) {
            target.classList.add("bw-tour-highlight");
            highlightedElement = target;

            target.scrollIntoView({
                behavior: "smooth",
                block: "center",
                inline: "nearest"
            });
        }

        speech.classList.remove("bw-tour-arrived");

        // Position after the scroll has had time to settle
        moveTimer = setTimeout(() => {
            if (closed) return;

            // Reserve space for the complete message
            description.textContent = step.description;
            positionSpeech();

            description.textContent = "";
            speech.classList.add("bw-tour-arrived");

            startTyping(step.description);
        }, 650);
    }

    function nextStep() {
        if (typedChars < fullText.length) {
            clearInterval(typingTimer);
            typingTimer = null;

            typedChars = fullText.length;
            description.textContent = fullText;
            updateNextButton();
            schedulePosition();
            return;
        }

        if (stepIndex === steps.length - 1) {
            closeTour();
        } else {
            showStep(stepIndex + 1);
        }
    }

    function previousStep() {
        if (stepIndex > 0) {
            showStep(stepIndex - 1);
        }
    }

    function handleKeydown(event) {
        if (event.key === "Escape") {
            closeTour();
        }
    }

    closeButton.addEventListener("click", closeTour);
    backdrop.addEventListener("click", closeTour);
    nextButton.addEventListener("click", nextStep);
    backButton.addEventListener("click", previousStep);

    window.addEventListener("resize", schedulePosition);
    window.addEventListener("scroll", schedulePosition, true);
    document.addEventListener("keydown", handleKeydown);

    dashboardMomoTour = { close: closeTour };

    showStep(0);
}



/* ==========================================
   QUICK ACCESS NAVIGATION
   ========================================== */

function setupQuickAccess() {
    const quickButtons =
        document.querySelectorAll(".quick-access-btn");

    quickButtons.forEach(button => {
        button.addEventListener("click", () => {
            const targetPage = button.dataset.target;

            const sidebarButton = document.querySelector(
                `.nav-btn[data-page="${targetPage}"]`
            );

            if (sidebarButton) {
                sidebarButton.click();

                window.scrollTo({
                    top: 0,
                    behavior: "smooth"
                });
            }
        });
    });
}


