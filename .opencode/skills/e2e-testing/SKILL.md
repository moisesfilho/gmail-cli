---
name: e2e-testing
description: End-to-end testing best practices with Playwright. Use when creating, reviewing, or refactoring E2E tests.
---

# E2E Testing with Playwright

## Guidelines

### Page Object Model (POM)

Abstract selectors and page actions into Page Object classes, keeping test logic separate from page structure.

### Resilient Selectors

Prefer accessible selectors (`getByRole`, `getByLabelText`, `getByPlaceholder`) or `getByTestId`. Avoid brittle CSS class or XPath selectors.

### Auto-Retrying Assertions

Use Playwright built-in assertions (`expect(locator).toBeVisible()`) which auto-wait. Never use `waitForTimeout` with fixed delays.

### Isolation

Each test must clean up its own state (local DB, storage) or be fully independent. No test should depend on another test's leftover state.

## Constraints

- Don't rely on exact HTML structure — use functional element characteristics
- Don't duplicate UI interactions in spec files — move them to Page Object classes
