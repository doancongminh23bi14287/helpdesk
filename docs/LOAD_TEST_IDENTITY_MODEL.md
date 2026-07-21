# Load-test identity model

The previous harness cached one token per persona, so multiple Locust users shared a per-user rate-limit bucket. The corrected harness allocates one synthetic account to each Locust instance from separate customer, staff and admin pools. Pool exhaustion fails closed.

Account entries use EMAIL|PASSWORD|EXPECTED_USER_ID|EXPECTED_ORG_ID|TOKEN. The optional prepared token keeps login out of the measured capacity phase. Each token has its own active session and is stored only on that Locust user.

The corrected 10-user run used 6 customer, 3 staff and 1 admin identities: 10 unique account IDs and 10 unique prepared tokens. Passwords, complete tokens and token contents are never logged or committed.
