# Business Rules

## Active Records
- A user is considered active if `users.status = 'active'` AND `users.end_date IS NULL`.
- Always filter for active users unless the user explicitly asks for inactive or all users.

## Currency
- All monetary amounts in the `orders` table are stored in USD.
- Use `orders.currency_code` only if joining with `exchange_rates`.
