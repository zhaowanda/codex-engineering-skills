# Order Export Requirement

Business purpose: Reduce manual order reconciliation time for operations by letting admins export the exact filtered order list used during review.

Scenario: Admin opens the order list page, applies filters, clicks the export action, and the system generates an Excel file from the same filtered result set.

Entry: Order list page export button.

Req: Admin needs to export filtered orders from the order list page.

Rule: only admin can export filtered results.

AC: exported file contains order id and status.

AC: non-admin user cannot see the export action.
