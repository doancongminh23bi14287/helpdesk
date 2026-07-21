# SEO security model

GSC and GA4 access is restricted to staff/admin users and resolved through the shared organisation-scoping policy. Customers cannot configure or inspect internal Google integrations. Tokens are encrypted at rest and are not part of API response models.

OAuth state is short-lived and one-time; callback handling must validate the stored organisation and initiating user before persisting a connection. Provider property selection must be validated against the provider-owned property list before storage. Provider errors are treated as external failures and must not affect ticketing or billing.
