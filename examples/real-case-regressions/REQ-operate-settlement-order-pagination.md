# Settlement order pagination

## Goal

Correct settlement order pagination on the existing settlement page without changing the provider API.

## Requirements

- Main entry: `src/views/device/replacementSettlement.vue`.
- Existing backend API is contract-confirm-only.
- `src/views/device/stockManager.vue` is forbidden as an implementation target.

## Acceptance Criteria

1. Changing page sends exactly one request with the selected page number and page size.
2. The table renders the returned page and total count.
3. Empty and failed requests retain stable pagination state.

## Constraints

- This is a frontend modification in one owner repository.
- Backend repositories are read-only compatibility references.
