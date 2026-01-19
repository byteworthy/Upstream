# Payrixa UI Architecture

This folder contains UI shell components and patterns for the product line.

## Structure

- **shell/**: Navigation, base layout helpers, and global UI patterns
- **components/**: Reusable widgets (empty states, filters, alert cards, etc.)
- **dashboards/**: Product-specific dashboard templates

## Patterns

### Empty States
All dashboards must show clear empty states when no data exists.

### Filters
Date range and filter patterns should be consistent across products.

### Navigation
Product navigation is conditional based on ProductConfig.enabled.

## Sprint 1 Status

Sprint 1 delivers scaffolding only. Dashboard templates show empty states, no business logic.
