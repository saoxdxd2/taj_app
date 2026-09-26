"""Type-safe translation keys.

Keys are Python attributes rather than free-form strings, so a typo is an
AttributeError at import time instead of a silent fallback to English in
production. This is the main reason the catalog cannot drift the way a
hand-maintained list of string keys does.

Structure follows 12_LOCALIZATION_STANDARD.md: module.section.element.
Each entry may carry a context string, which is what a translator needs
to choose the right word without guessing how it is used.
"""
from typing import NamedTuple


class Entry(NamedTuple):
    """One translatable string plus the context a translator needs."""
    key: str
    context: str = ""


class _Catalog:
    """Base that exposes every key as a dotted attribute path."""

    @classmethod
    def all_keys(cls) -> list:
        """Returns every Entry defined under this catalog, recursively."""
        found = []
        for name, value in vars(cls).items():
            if name.startswith("_"):
                continue
            if isinstance(value, Entry):
                found.append(value)
            elif isinstance(value, type) and issubclass(value, _Catalog):
                found.extend(value.all_keys())
        return found


class Common(_Catalog):
    save = Entry("common.action.save", "Save button")
    cancel = Entry("common.action.cancel", "Cancel button")
    close = Entry("common.action.close", "Close button")
    delete = Entry("common.action.delete", "Delete button")
    edit = Entry("common.action.edit", "Edit button")
    add = Entry("common.action.add", "Add button")
    search = Entry("common.action.search", "Search button")
    refresh = Entry("common.action.refresh", "Reload data from the database")
    retry = Entry("common.action.retry", "Retry a failed operation")
    export = Entry("common.action.export", "Export to a file")
    import_ = Entry("common.action.import", "Import from a file")
    yes = Entry("common.action.yes", "Affirmative answer")
    no = Entry("common.action.no", "Negative answer")
    ok = Entry("common.action.ok", "Confirmation")
    all_ = Entry("common.filter.all", "No filter applied")
    loading = Entry("common.status.loading", "Shown while data loads")
    none = Entry("common.value.none", "No value")
    unknown = Entry("common.value.unknown", "Value could not be determined")
    currency = Entry("common.currency.dh", "Moroccan dirham symbol")
    date_format = Entry("common.format.date", "Short date, e.g. 26/09/2026")
    datetime_format = Entry("common.format.datetime", "Date and time")
    percent = Entry("common.format.percent", "Percentage, e.g. 20%")


class Auth(_Catalog):
    title = Entry("auth.window.title", "Login window title")
    subtitle = Entry("auth.login.subtitle", "Shown above the login form")
    username = Entry("auth.field.username", "Username input label")
    password = Entry("auth.field.password", "Password input label")
    sign_in = Entry("auth.action.sign_in", "Submit the login form")
    failed = Entry("auth.error.failed", "Wrong username or password")
    error = Entry("auth.error.generic", "Unexpected authentication error")
    locked = Entry(
        "auth.error.locked",
        "Too many failed attempts; the account is temporarily locked",
    )
    change_password = Entry("auth.action.change_password", "Open password change")
    create_user = Entry("auth.action.create_user", "Open the create-user form")
    user_management = Entry("auth.group.user_management", "Settings section")
    account_security = Entry("auth.group.account_security", "Settings section")
    username_taken = Entry("auth.error.username_taken", "Username already exists")
    weak_password = Entry(
        "auth.error.weak_password",
        "Password does not meet complexity rules",
    )


class Navigation(_Catalog):
    dashboard = Entry("nav.dashboard", "Sidebar item")
    calendar = Entry("nav.calendar", "Sidebar item")
    inventory = Entry("nav.inventory", "Sidebar item")
    crm = Entry("nav.crm", "Sidebar item")
    suppliers = Entry("nav.suppliers", "Sidebar item")
    purchasing = Entry("nav.purchasing", "Sidebar item")
    finance = Entry("nav.finance", "Sidebar item")
    sales = Entry("nav.sales", "Sidebar item")
    analytics = Entry("nav.analytics", "Sidebar item")
    settings = Entry("nav.settings", "Sidebar item")
    sign_out = Entry("nav.sign_out", "Sign out of the application")


class Inventory(_Catalog):
    group = Entry("inventory.group.products", "Section title")
    product = Entry("inventory.entity.product", "Product, singular")
    products = Entry("inventory.entity.products", "Product, plural")
    add_product = Entry("inventory.action.add_product", "Create a product")
    sku = Entry("inventory.field.sku", "Stock keeping unit")
    name = Entry("inventory.field.name", "Product name")
    category = Entry("inventory.field.category", "Product category")
    brand = Entry("inventory.field.brand", "Product brand")
    purchase_price = Entry("inventory.field.purchase_price", "Cost price")
    sale_price = Entry("inventory.field.sale_price", "Store selling price")
    website_price = Entry(
        "inventory.field.website_price", "Selling price on the website"
    )
    vat_rate = Entry("inventory.field.vat_rate", "Value added tax percentage")
    stock = Entry("inventory.field.stock", "Current quantity in stock")
    min_quantity = Entry(
        "inventory.field.min_quantity", "Reorder threshold quantity"
    )
    type = Entry("inventory.field.type", "Product type")
    state = Entry("inventory.field.state", "Product lifecycle state")
    low_stock = Entry("inventory.status.low_stock", "At or below the threshold")
    attributes = Entry("inventory.group.attributes", "Dynamic attribute section")
    add_attribute = Entry("inventory.action.add_attribute", "Define an attribute")
    delete_attribute = Entry(
        "inventory.action.delete_attribute", "Remove an attribute definition"
    )
    delete_confirm = Entry(
        "inventory.confirm.delete_product",
        "Confirmation before deleting a product",
    )
    select_product = Entry("inventory.hint.select_product", "Choose a product")


class Crm(_Catalog):
    group = Entry("crm.group.customers", "Section title")
    customer = Entry("crm.entity.customer", "Customer, singular")
    customers = Entry("crm.entity.customers", "Customer, plural")
    add_customer = Entry("crm.action.add_customer", "Create a customer")
    company_name = Entry("crm.field.company_name", "Registered company name")
    ice_number = Entry("crm.field.ice_number", "Moroccan ICE identifier")
    rc_number = Entry("crm.field.rc_number", "Registre de Commerce")
    if_number = Entry("crm.field.if_number", "Identifiant Fiscal")
    phone = Entry("crm.field.phone", "Phone number")
    email = Entry("crm.field.email", "Email address")
    address = Entry("crm.field.address", "Street address")
    city = Entry("crm.field.city", "City")
    balance = Entry("crm.field.balance", "Outstanding balance")


class Suppliers(_Catalog):
    group = Entry("suppliers.group.suppliers", "Section title")
    supplier = Entry("suppliers.entity.supplier", "Supplier, singular")
    suppliers = Entry("suppliers.entity.suppliers", "Supplier, plural")
    add_supplier = Entry("suppliers.action.add_supplier", "Create a supplier")
    contact_name = Entry("suppliers.field.contact_name", "Primary contact")
    tax_id = Entry("suppliers.field.tax_id", "Tax identifier")
    payment_terms = Entry("suppliers.field.payment_terms", "Agreed payment terms")
    delete_confirm = Entry(
        "suppliers.confirm.delete", "Confirmation before deleting a supplier"
    )



class Purchasing(_Catalog):
    group = Entry("purchasing.group.purchases", "Section title")
    purchase = Entry("purchasing.entity.purchase", "Purchase order, singular")
    purchases = Entry("purchasing.entity.purchases", "Purchase order, plural")
    add_purchase = Entry("purchasing.action.add_purchase", "Create a purchase")
    reference = Entry("purchasing.field.reference", "Purchase order reference")
    supplier = Entry("purchasing.field.supplier", "Supplier of the goods")
    unit_cost = Entry("purchasing.field.unit_cost", "Cost per unit")
    quantity = Entry("purchasing.field.quantity", "Quantity ordered")
    total = Entry("purchasing.field.total", "Order total")
    state = Entry("purchasing.field.state", "Order lifecycle state")
    validate = Entry("purchasing.action.validate", "Confirm and post the order")
    delete_confirm = Entry(
        "purchasing.confirm.delete", "Confirmation before deleting an order"
    )


class Sales(_Catalog):
    group = Entry("sales.group.invoices", "Section title")
    invoice = Entry("sales.entity.invoice", "Legal invoice, singular")
    invoices = Entry("sales.entity.invoices", "Legal invoice, plural")
    quotation = Entry("sales.entity.quotation", "Customer quotation, singular")
    add_invoice = Entry("sales.action.add_invoice", "Create an invoice")
    invoice_number = Entry("sales.field.invoice_number", "Sequential invoice number")
    customer = Entry("sales.field.customer", "Billed customer")
    due_date = Entry("sales.field.due_date", "Payment due date")
    item = Entry("sales.entity.line_item", "A line on an invoice")
    unit_price = Entry("sales.field.unit_price", "Price per unit")
    warranty = Entry("sales.field.warranty_months", "Warranty in months")
    subtotal = Entry("sales.field.subtotal", "Total before tax")
    vat = Entry("sales.field.vat", "Value added tax")
    total = Entry("sales.field.total", "Total including tax")
    balance = Entry("sales.field.balance", "Amount still owed")
    state = Entry("sales.field.state", "Invoice lifecycle state")
    channel = Entry("sales.field.channel", "Sales channel the invoice came from")
    validate = Entry("sales.action.validate_invoice", "Post the invoice")
    record_payment = Entry("sales.action.record_payment", "Register a payment")
    print_invoice = Entry("sales.action.print_invoice", "Print or export the PDF")
    delete_confirm = Entry(
        "sales.confirm.delete_invoice", "Confirmation before deleting an invoice"
    )
    payment_method = Entry("sales.field.payment_method", "How the money was paid")
    payment_amount = Entry("sales.field.payment_amount", "Amount received")


class Finance(_Catalog):
    group = Entry("finance.group.journal", "Section title")
    journal = Entry("finance.entity.journal_entry", "Journal entry")
    expenses = Entry("finance.group.expenses", "Section title")
    checks = Entry("finance.group.checks", "Section title")
    add_expense = Entry("finance.action.add_expense", "Record an expense")
    add_check = Entry("finance.action.add_check", "Record a check")
    amount = Entry("finance.field.amount", "Monetary amount")
    category = Entry("finance.field.category", "Expense category")
    direction = Entry("finance.field.direction", "Incoming or outgoing check")
    status = Entry("finance.field.status", "Check or entry status")
    revenue = Entry("finance.field.revenue", "Revenue excluding tax")
    cost = Entry("finance.field.cost", "Cost of goods sold")
    margin = Entry("finance.field.margin", "Gross margin")
    profit = Entry("finance.field.profit", "Net profit")
    delete_confirm = Entry(
        "finance.confirm.delete", "Confirmation before deleting a financial record"
    )


class Analytics(_Catalog):
    group = Entry("analytics.group.reports", "Section title")
    title = Entry("analytics.title", "Analytics page heading")
    period = Entry("analytics.field.period", "Reporting period")
    sales_trend = Entry("analytics.chart.sales_trend", "Sales over time")
    top_products = Entry("analytics.chart.top_products", "Best selling products")
    revenue_by_channel = Entry(
        "analytics.chart.revenue_by_channel", "Store versus website revenue"
    )
    forecast = Entry("analytics.chart.forecast", "Demand forecast")
    no_data = Entry("analytics.empty.no_data", "Shown when a chart has no data")


class Settings(_Catalog):
    group = Entry("settings.group.general", "Section title")
    backup = Entry("settings.group.backup", "Section title")
    support = Entry("settings.group.support", "Section title")
    preferences = Entry("settings.group.preferences", "System preferences section")
    company = Entry("settings.group.company", "Company identity section")
    language = Entry("settings.field.language", "Interface language selector")
    create_backup = Entry("settings.action.create_backup", "Back up the database")
    restore_backup = Entry("settings.action.restore_backup", "Restore from a backup")
    restore_external = Entry(
        "settings.action.restore_external", "Restore from a backup file"
    )
    available_backups = Entry("settings.label.available_backups", "Backup list")
    export_diagnostics = Entry(
        "settings.action.export_diagnostics", "Export a support bundle"
    )
    optimize_database = Entry("settings.action.optimize_database", "Compact the file")
    run_health_checks = Entry("settings.action.run_health_checks", "Diagnose the system")
    change_sync_folder = Entry(
        "settings.action.change_sync_folder", "Choose the website sync folder"
    )
    export_catalog = Entry(
        "settings.action.export_catalog", "Send the product catalog to the website"
    )
    import_prices = Entry(
        "settings.action.import_prices", "Import price updates from the website"
    )
    username = Entry("settings.table.username", "User table column")
    role = Entry("settings.table.role", "User table column")
    status = Entry("settings.table.status", "User table column")
    enable_selected = Entry(
        "settings.action.enable_selected", "Toggle the selected account"
    )
    setting = Entry("settings.table.setting", "Preferences table column")
    value = Entry("settings.table.value", "Preferences table column")
    description = Entry("settings.table.description", "Preferences table column")
    retention_count = Entry(
        "settings.pref.backup_retention", "How many backups to keep"
    )
    min_disk_space = Entry(
        "settings.pref.min_disk_space", "Free disk space needed for a backup"
    )
    log_rotation = Entry("settings.pref.log_rotation", "Log rotation size")
    log_retention = Entry("settings.pref.log_retention", "How long logs are kept")
    default_warranty = Entry(
        "settings.pref.default_warranty", "Default warranty in months"
    )
    invoice_prefix = Entry(
        "settings.pref.invoice_prefix", "Prefix for generated invoice numbers"
    )
    saved = Entry("settings.msg.saved", "Confirmation after saving preferences")
    save_failed = Entry("settings.error.save_failed", "Could not save preferences")


class Migration(_Catalog):
    failed_title = Entry("migration.error.title", "Title of the failed-upgrade dialog")
    failed_body = Entry(
        "migration.error.body", "Explains that no further changes were applied"
    )
    with_backup = Entry(
        "migration.error.with_backup", "Shown when a pre-upgrade backup is available"
    )
    without_backup = Entry(
        "migration.error.without_backup", "Shown when no pre-upgrade backup exists"
    )
    retry = Entry("migration.action.retry", "Run the upgrade again")
    restore = Entry("migration.action.restore", "Restore the pre-upgrade backup")
    exit = Entry("migration.action.exit", "Close the application")
    restore_failed = Entry(
        "migration.error.restore_failed", "The backup could not be restored"
    )
    retry_failed = Entry(
        "migration.error.retry_failed", "The upgrade failed again after a retry"
    )


class Dashboard(_Catalog):
    title = Entry("dashboard.title", "Dashboard heading")
    today_sales = Entry("dashboard.kpi.today_sales", "Sales recorded today")
    month_sales = Entry("dashboard.kpi.month_sales", "Sales this month")
    outstanding = Entry("dashboard.kpi.outstanding", "Money still owed")
    stock_value = Entry("dashboard.kpi.stock_value", "Value of stock on hand")
    low_stock_count = Entry(
        "dashboard.kpi.low_stock_count", "Products at or below the threshold"
    )
    recent_invoices = Entry("dashboard.table.recent_invoices", "Recent activity")
    welcome = Entry("dashboard.welcome", "Greets the signed-in user by name")


class Pagination(_Catalog):
    previous = Entry("pagination.previous", "Go to the previous page")
    next = Entry("pagination.next", "Go to the next page")
    status = Entry("pagination.status", "e.g. Showing 1-100 of 250")


class Root(_Catalog):
    """Namespace exposing every module catalog as an attribute."""

    common = Common
    auth = Auth
    nav = Navigation
    inventory = Inventory
    crm = Crm
    suppliers = Suppliers
    purchasing = Purchasing
    sales = Sales
    finance = Finance
    analytics = Analytics
    settings = Settings
    migration = Migration
    dashboard = Dashboard
    pagination = Pagination

    @classmethod
    def all_keys(cls):
        """Every Entry in every module catalog."""
        found = []
        for name, value in vars(cls).items():
            if name.startswith("_"):
                continue
            if isinstance(value, type) and issubclass(value, _Catalog):
                found.extend(value.all_keys())
        return found


# The catalog object used in UI code: tr.common.action.save
tr = Root
