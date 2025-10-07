# AGENTS.md

## Commands

- Do not run any commands in the agent.

## Tests

- Do not write new tests unless specifically asked to.
- Do not run any tests unless specifically asked to.

## Variable Naming Guidelines
Use descriptive, full-word variable names that clearly communicate purpose and context. Avoid abbreviations and single-letter variables.

Bad:
```python
d = datetime.now().strftime("%Y-%m-%d")
articles = get_articles(d)
```

Good:
```python
current_date = datetime.now().strftime("%Y-%m-%d")
articles = get_articles_by_date(current_date)
```

### Provide Context in Names
Add specific context when the format or type matters to the implementation.

Example:
```python
current_date_iso_format = datetime.now().strftime("%Y-%m-%d")
time_since_product_creation = product.created_at - current_date
```

### Use Constants
Extract unchanging values into constants using UPPER_CASE naming.

Example:
```python
MAX_LOGIN_ATTEMPTS = 5
DEFAULT_TIMEOUT_MS = 10000
DATE_FORMAT = "%Y-%m-%d"
SALES_TAX_RATE = 0.08
```

### Use Intermediary Variables
Break down complex operations with descriptive intermediate variables instead of accessing array indices directly.

Bad:
```python
match = re.match(r'^([^,]+),\s*(.+?)$', product_info)
if match:
    create_product(match.group(1), match.group(2))
```
Good:
```python
match = re.match(r'^([^,]+),\s*(.+?)$', product_info)
if match:
    name, sku = match.groups()
    create_product(name, sku)
```

### Naming Conventions
- Use `is_`, `has_`, `can_` prefixes for boolean variables
- Include "date" in variable names that represent dates
- Use snake_case for variables and functions
- Use PascalCase for classes

Example:
```python
is_available = True
has_permission = user.check_access()
can_edit = is_available and has_permission
```

### Keep Variable Lifespan Short
Define variables close to where they're used to reduce cognitive load.

Bad:
```python
current_date = datetime.now()
date_and_unit = parse_input(user_input)
value, unit = date_and_unit.split(' ')
if not is_valid_unit(unit):
    return
to_date = current_date - timedelta(**{unit: int(value)})
```

Good:
```python
date_and_unit = parse_input(user_input)
value, unit = date_and_unit.split(' ')
if not is_valid_unit(unit):
    return
current_date = datetime.now()
to_date = current_date - timedelta(**{unit: int(value)})
```

## Naming Guidelines for AI Coding

### Core Principle
Ask yourself: "Will I understand this without my current context?" Name things after what they do, not how they're used.

### Boolean Values
Prefix with `is`, `has`, or `can`:

```python
def can_delete(post):
    # Make a check...
    return True

if can_delete(post):
    # execute logic
```

### Avoid Generic Names
Never use `data`, `info`, `manager`. Be specific:

```python
# Bad
def process_data(data):
    pass

# Good
def calculate_customer_lifetime_value(customer):
    pass
```

### Function Names
Include all necessary context without being verbose:

```python
# Bad - missing context
def add_to_date(date, month):
    pass

# Good - clear context
def add_month_to_date(date, month):
    pass

# Too verbose
def add_number_of_months_to_date(date, month):
    pass
```

### When Naming is Hard
If you can't name it clearly, split the function into smaller, focused parts:

```python
# Instead of one complex function
def get_access_details(user):
    can_access = can_access_content(user)
    return {"allowed": can_access, "message": get_access_message(user)}

def can_access_content(user):
    if user.role == 'admin':
        return True
    return is_subscription_valid(user)

def is_subscription_valid(user):
    return user.subscription_status == 'active'
```

### Consistency Rules
- Use the same verbs across the codebase (fetch, not mix of fetch/get/retrieve)
- Use the same nouns for the same concepts (order vs purchase)
- Name variables after the functions that create them: messages = get_messages()

### Variable Lifespan
Longer-lived variables need more descriptive names:

```python
# Short-lived in small scope
items.map(lambda n: n * 2)

# Long-lived across functions
customer_lifetime_values = calculate_metrics(customers)
```

### File Naming
Use specific names over generic ones:

- `date_utils.py` not `utils.py`
- `user_repository.py` not `repository.py`


## Conditional Logic Guidelines

### Avoid Else Statements - Use Guard Clauses
Structure code with the main execution path at the lowest indentation level. Handle exceptional cases first with early returns.

```python
# Instead of if-else
if user.is_authenticated():
    return redirect('/dashboard')
else:
    return render_template('login.html')

# Use guard clauses
if not user.is_authenticated():
    return render_template('login.html')

return redirect('/dashboard')
```

### Replace Simple Conditionals with Direct Assignment
When both branches call the same function with different values, assign the value directly.

```python
# Instead of
if message_type == 'typing':
    set_typing_status(True)
else:
    set_typing_status(False)

# Use direct assignment
is_typing = message_type == 'typing'
set_typing_status(is_typing)
```

### Use Dictionaries for Multiple Equal Conditions
Replace switch-like logic with dictionary lookups when all conditions are equally likely.

```python
# Instead of multiple elif statements
message_handlers = {
    'typing': mark_user_typing,
    'new_message': append_message,
    'user_offline': change_user_status
}

handler = message_handlers.get(message_type)
if handler:
    handler(payload)
```

### Validate Input Before Processing
Always validate data structure before reaching conditional logic to prevent errors.

```python
try:
    validated_data = schema.validate(raw_data)
    process_message(validated_data)
except ValidationError:
    logger.error("Invalid message format")
    return
```


## Use Empty Collections

Always default to empty collections instead of null/None values to reduce complexity and eliminate unnecessary conditional checks throughout the codebase.

### Implementation Guidelines

- Initialize arrays, lists, and dictionaries as empty collections rather than None
- Handle empty states at the data source level, not at every usage point
- Remove conditional checks when working with collections that are guaranteed to be non-None

### Examples

```python
# ❌ Avoid - requires checks everywhere
def get_products():
    products = fetch_from_db()
    return products  # Could be None

# Usage requires defensive checks
products = get_products()
if products:
    prices = [item.price for item in products]

# ✅ Preferred - return empty list
def get_products():
    products = fetch_from_db()
    return products or []

# Usage is simplified
products = get_products()
prices = [item.price for item in products]  # Always works

# ✅ State initialization
items = []  # Not None
user_data = {}  # Not None

# ✅ Function parameters with defaults
def process_items(items: list = None):
    items = items or []  # Convert None to empty list immediately
    return [item.upper() for item in items]
```

### Benefits

- Eliminates null checks throughout the codebase
- Reduces cognitive load when reading code
- Prevents None-related runtime errors
- Makes iteration and collection operations always safe


## Code Organization
Write functions at a single level of abstraction. Each function should do one thing only.

### Bad Example
```python
def process_user_data(users):
    processed_users = []

    # Validate and clean data
    for user in users:
        if user.get('email') and '@' in user['email']:
            clean_email = user['email'].strip().lower()
            if len(user.get('name', '')) > 0:
                clean_name = user['name'].strip().title()

                # Calculate age from birthdate
                if user.get('birthdate'):
                    today = datetime.now()
                    birth = datetime.strptime(user['birthdate'], '%Y-%m-%d')
                    age = today.year - birth.year

                    processed_users.append({
                        'email': clean_email,
                        'name': clean_name,
                        'age': age
                    })

    return processed_users
```

### Good Example
```python
def process_user_data(users):
    valid_users = filter_valid_users(users)
    cleaned_users = clean_user_data(valid_users)
    return add_calculated_fields(cleaned_users)

def filter_valid_users(users):
    return [user for user in users if is_valid_user(user)]

def is_valid_user(user):
    return (user.get('email') and '@' in user['email']
            and len(user.get('name', '')) > 0)

def clean_user_data(users):
    return [clean_single_user(user) for user in users]

def clean_single_user(user):
    return {
        'email': user['email'].strip().lower(),
        'name': user['name'].strip().title(),
        'birthdate': user['birthdate']
    }
```

### Testing
Write tests for each function. Single-responsibility functions are easier to test and debug.

### Naming
Use descriptive function names that clearly indicate what the function does at its level of abstraction.

## Function Naming and Design

### Use Strong Verbs
Start function names with clear action verbs followed by the entity:
```python
# Good
def get_user_by_id(user_id: str):
    pass

def calculate_total_price(items: list):
    pass

def sync_user_data():
    pass

# Avoid ambiguous names
def user_price():  # unclear action
    pass
```

### Avoid "And" in Function Names
Split functions that try to do multiple things:
```python
# Bad - doing too much
def calculate_total_and_format_receipt(items):
    total = sum(item.price * item.quantity for item in items)
    receipt = f"Total: ${total:.2f}"
    return receipt

# Good - single responsibility
def calculate_total(items):
    return sum(item.price * item.quantity for item in items)

def format_receipt(items, total):
    return f"Total: ${total:.2f}"
```

### Function Parameters
- Keep optional parameters at the end
- Use objects/dictionaries for 3+ parameters
- Eliminate redundant parameters

```python
# Bad - redundant parameters
def cancel_booking(booking_id: str, should_execute_callback: bool, callback=None):
    if should_execute_callback and callback:
        callback()

# Good - callback presence indicates intent
def cancel_booking(booking_id: str, callback=None):
    if callback:
        callback()

# For multiple parameters, use dictionary
def create_order(order_data: dict):
    # order_data = {
    #     'product_id': 'abc123',
    #     'quantity': 2,
    #     'is_member': False,
    #     'discount_code': 'SAVE10'
    # }
    pass
```

## Loop Guidelines
- Use list comprehensions and built-in functions instead of for loops when possible
- Chain operations for readability: `filter()`, `map()`, `reduce()`
- Name collections with plural nouns, iterate with singular

```python
# Good - functional approach
total_active_balance = sum(
    get_user_balance(user)
    for user in users
    if is_active_user(user)
)

# Good - descriptive iteration
products = get_all_products()
active_products = [product for product in products if product.is_active]

# Good - nested loops with clear naming
food_groups = [
    ["banana", "avocado", "tomato"],
    ["steak", "sausage"]
]

for food_group_id, food_group in enumerate(food_groups):
    for food_id, food in enumerate(food_group):
        process_food(food, food_group_id, food_id)
```

## Code Quality and Performance Guidelines

### Prioritize Maintainability Over Performance
- Write clear, readable code that communicates intent
- Choose descriptive variable names and function names
- Break complex operations into smaller, understandable steps
- Only optimize for performance when domain requirements demand it

### Code Style
- Use Python's functional patterns where appropriate (map, filter, comprehensions)
- Prefer explicit over implicit operations
- Write self-documenting code with clear function signatures

### Performance Considerations
- Understand your domain's actual performance requirements
- Consider environmental context (database queries, I/O operations, memory usage)
- Optimize only the critical paths that impact user experience
- Measure before optimizing

### Examples

**Favor readability:**
```python
# Preferred - clear intent
total_revenue = (
    apply_discount(product)
    for product in products
)
total = sum(calculate_revenue(item) for item in total_revenue)

# Avoid unless performance is critical
total = 0
for product in products:
    discounted_price = product.price * 0.9
    total += discounted_price
```

**Consider environmental context:**
```python
# Batch database operations
user_ids = [user.id for user in users]
user_data = database.fetch_batch(user_ids)

# Instead of individual queries
for user in users:
    user_data = database.fetch_single(user.id)  # Avoid
```

## Error Prevention Philosophy

Program errors out of existence by designing code that eliminates the need for exception handling wherever possible.

### Default Values Over Null Checks

Use default parameters and fallback values instead of conditional logic:

```python
# Avoid this
def greet(name):
    if not name:
        return None
    return f"Hello, {name}!"

# Prefer this
def greet(name="user"):
    return f"Hello, {name}!"
```

### Graceful Data Handling

Return appropriate default types when data is missing:

```python
fruit_colors = {
    'apple': 'red',
    'banana': 'yellow',
    'grape': 'purple'
}

def get_color(fruit):
    return fruit_colors.get(fruit, 'unknown')
```

### Handle Errors at the Source

Catch and mask errors as close to their origin as possible:

```python
def fetch_data():
    try:
        return some_async_operation()
    except Exception:
        return []

def get_stock_history(stock):
    try:
        history, status = get_history_from_api()
        return {
            'name': stock,
            'status': status or 'N/A',
            'history': history or []
        }
    except Exception:
        return {
            'name': stock,
            'status': 'N/A',
            'history': []
        }
```

### Validate Early

Use validation at entry points to prevent errors downstream:

```python
from pydantic import BaseModel, validator

class UserSchema(BaseModel):
    name: str
    email: str
    age: int

    @validator('name')
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Name is required')
        return v

# Validate at API boundary, not in business logic
def create_user(user_data: UserSchema):
    # Business logic can assume valid data
    return user_service.create(user_data.dict())
```


## Code Organization and Awareness

Keep functions focused and limit what they "know" about. A function should only be aware of details necessary for its specific responsibility.

### Reduce Function Knowledge

**Bad - Function knows too much:**
```python
def process_order(order_id: str):
    # Direct database access
    order = db.execute(f"SELECT * FROM orders WHERE id = {order_id}")

    # Direct payment processing
    payment = stripe.charge(order.customer_id, order.amount)

    # Direct email sending
    smtp.send_email(order.email, "Order confirmed", f"Order {order_id} processed")
```

**Good - Separated concerns:**
```python
def process_payment(order: Order, discount_code: str = None) -> PaymentResult:
    amount = calculate_final_amount(order, discount_code)
    return payment_processor.charge(order.customer_id, amount)

def process_order(order_id: str):
    order = get_order(order_id)
    payment_result = process_payment(order)
    send_confirmation_email(order)
```

### Use Dependency Injection

**Bad - Direct dependency:**
```python
import logging

logger = logging.getLogger(__name__)

def process_data(data):
    logging.info("Processing started")
    # process data
    logging.info("Processing completed")
```

**Good - Injected dependency:**
```python
def process_data(data, logger):
    logger.info("Processing started")
    # process data
    logger.info("Processing completed")
```

### Create Simple Wrappers

**Bad - Direct third-party usage:**
```python
import boto3

def upload_file(file_path: str):
    s3 = boto3.client('s3')
    s3.upload_file(file_path, 'bucket-name', 'key')
```

**Good - Abstracted wrapper:**
```python
def upload_file(file_path: str, uploader_func):
    uploader_func(file_path)

# Wrapper handles AWS specifics
def aws_uploader(file_path: str):
    s3 = boto3.client('s3')
    s3.upload_file(file_path, 'bucket-name', 'key')
```

### Key Principle

Ask: "Do I need to know this implementation detail to modify this function?" If no, extract it or inject it as a dependency.
