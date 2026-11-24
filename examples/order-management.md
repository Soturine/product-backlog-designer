# Synthetic example — order registration

This fixture is fictional and unrelated to any real organization.

## Source
REQ-01: Operator can create a pending order with a customer identifier and at least one item.
REQ-02: An incomplete order must be rejected without persisting it.
REQ-03: A successfully saved order is visible in the pending order list.
REQ-04: Payment processing is out of scope.

## Epic EP-001 — Digital order management
**Objective:** register and consult pending orders.
**Context:** operators need organized requests.
**In scope:** registration and pending list.
**Out of scope:** payment processing.

### Feature FE-001 — Pending order registration
Allow operators to register valid orders and see their saved requests.

#### Story US-001 — Register a pending order
**Eu como** operador, **gostaria que** o sistema registrasse pedidos pendentes, **para** organizar as solicitações.

Acceptance criteria:
- AC-001: An order with customer ID and at least one item can be saved. (REQ-01)
- AC-002: An incomplete order is rejected and not persisted. (REQ-02)
- AC-003: A saved order appears in the pending list. (REQ-03)

Tasks:
- TK-001: Design order input and required fields (AC-001).
- TK-002: Implement validation and persistence (AC-001/002); architecture to confirm.
- TK-003: Implement pending-list retrieval (AC-003).
- TK-004: Verify valid and incomplete orders and list visibility (AC-001/002/003; Testing).

Estimates, dates and assignees are unknown. REQ-04 is OUT_OF_SCOPE. This example is illustrative, not a benchmark result.
