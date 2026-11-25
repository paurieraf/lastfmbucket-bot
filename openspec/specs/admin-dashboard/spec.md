# admin-dashboard Specification

## Purpose

Provides a hardened, web-based administrative dashboard for operating LastfmBucket Bot, allowing authenticated administrators to monitor bot metrics and safely inspect or manage users, chats, command logs, group crowns, and chat memberships.

## Requirements

### Requirement: Explicit Environment Loading and Weak Password Detection
The admin dashboard MUST explicitly load environment configuration from `.env` at startup rather than relying on side effects of other imported modules. When the configured admin password is empty or equals the default placeholder `"changeme"`, the system MUST emit a prominent security warning log without ever logging raw passwords or secret keys.

#### Scenario: Default password triggers startup warning
- **WHEN** the admin dashboard starts with `ADMIN_PASSWORD` unset or set to `"changeme"`
- **THEN** the system logs a prominent warning advising the operator to set a strong `ADMIN_PASSWORD`
- **AND** the warning log does not contain the secret key or raw password value

#### Scenario: Empty password triggers startup warning
- **WHEN** the admin dashboard starts with `ADMIN_PASSWORD` set to an empty string
- **THEN** the system logs a prominent warning indicating that `ADMIN_PASSWORD` is weak or empty

#### Scenario: Custom strong password emits no weak-password warning
- **WHEN** the admin dashboard starts with `ADMIN_PASSWORD` set to a non-empty value other than `"changeme"`
- **THEN** the system does not emit a weak-password warning

### Requirement: Constant-Time Authentication and Route Protection
The admin dashboard MUST verify login credentials using constant-time comparison for both username and password. Every administrative route other than `/login` MUST require an authenticated session and redirect unauthenticated visitors to `/login`.

#### Scenario: Valid credentials authenticate the operator
- **WHEN** an operator submits the configured username and password on `/login`
- **THEN** credentials are verified in constant time, the session is marked authenticated, and the operator is redirected to `/`

#### Scenario: Invalid credentials are rejected
- **WHEN** an operator submits an incorrect username or password on `/login`
- **THEN** authentication fails, the session remains unauthenticated, and an error notification is shown

#### Scenario: Unauthenticated access to protected pages
- **WHEN** an unauthenticated visitor opens `/`, `/users`, `/chats`, `/logs`, `/crowns`, or `/members`
- **THEN** the system redirects the visitor to `/login` without rendering protected data

### Requirement: Login Brute-Force Rate Limiting
The `/login` endpoint MUST enforce an in-memory per-client rate limit keyed by client IP address (with session fallback when IP is unavailable). After exceeding the allowed number of failed login attempts within the tracking window, subsequent login attempts from that client MUST be blocked for a cooldown period.

#### Scenario: Repeated failures trigger temporary lockout
- **WHEN** a client submits failed credentials more than the configured maximum attempts within the rate-limit window
- **THEN** the client is locked out for the cooldown duration and receives a rate-limit error message

#### Scenario: Locked-out client cannot authenticate during cooldown
- **WHEN** a locked-out client submits credentials (even valid ones) before the cooldown expires
- **THEN** the login attempt is rejected with a lockout message indicating the client must wait

#### Scenario: Lockout expires after cooldown window
- **WHEN** the cooldown period has elapsed for a previously locked-out client and the client submits valid credentials
- **THEN** authentication succeeds and the failure history for that client is cleared

#### Scenario: Successful login clears prior failed attempts
- **WHEN** a client fails fewer than the maximum allowed attempts and then logs in successfully
- **THEN** the client's failed-attempt history is reset

### Requirement: Confirmation-Gated Destructive Actions
Destructive delete actions in the admin dashboard MUST require explicit operator confirmation via a modal dialog before modifying the database.

#### Scenario: Canceling user deletion preserves the user
- **WHEN** an operator clicks the delete action for a user on `/users` and clicks Cancel in the confirmation dialog
- **THEN** the user record and its related records remain unchanged in the database

#### Scenario: Confirming user deletion removes the user and refreshes the view
- **WHEN** an operator clicks the delete action for a user on `/users`, reviews the cascade-deletion warning, and confirms deletion
- **THEN** the user record is deleted from the database, a confirmation notification is displayed, and the users table refreshes

#### Scenario: Confirming crown deletion removes the crown
- **WHEN** an operator clicks the delete action for a crown on `/crowns` and confirms deletion in the dialog
- **THEN** the crown record is deleted from the database, a confirmation notification is displayed, and the crowns table refreshes

### Requirement: Unique Row Identity and Eagerly Joined Queries
All data tables in the admin dashboard MUST key rows by each record's unique database `id`. Queries for tables displaying related `Chat` or `User` attributes MUST eagerly join those tables in a single query rather than executing N+1 per-row queries.

#### Scenario: Multiple command logs with identical timestamps render distinctly
- **WHEN** two or more `CommandLog` records share the exact same Unix timestamp
- **THEN** the Dashboard recent commands table and `/logs` table include each record's unique `id` as the row key so all rows render without collision

#### Scenario: Command logs load chat details without N+1 queries
- **WHEN** the Dashboard or `/logs` fetches multiple `CommandLog` records (including records with and without an associated `Chat`)
- **THEN** all command rows and their chat name and type are retrieved via a single joined query with safe fallback placeholders (`"-"`) when `chat` is null

#### Scenario: Crowns and chat members load related entities without N+1 queries
- **WHEN** `/crowns` or `/members` fetches multiple records
- **THEN** related `Chat` and `User` fields are retrieved via a single joined query with safe fallback placeholders when optional fields are empty

### Requirement: Dashboard Summary Metrics and Shared Navigation
All authenticated admin pages MUST display a single consistent navigation header linking to Dashboard (`/`), Users (`/users`), Chats (`/chats`), Command Logs (`/logs`), Crowns (`/crowns`), Members (`/members`), and Logout. The Dashboard MUST display summary cards for Total Users, Linked Users, Total Chats, Total Crowns, Total Commands, and Commands Today.

#### Scenario: Dashboard displays complete summary counts
- **WHEN** an authenticated operator visits `/`
- **THEN** the Dashboard displays accurate counts for Total Users, Linked Users (users with a non-empty Last.fm username), Total Chats, Total Crowns, Total Commands, and Commands Today, followed by the 10 most recent commands

#### Scenario: Navigation header is consistent across all authenticated pages
- **WHEN** an authenticated operator navigates between `/`, `/users`, `/chats`, `/logs`, `/crowns`, and `/members`
- **THEN** every page renders the shared navigation header with links to all six sections and a Logout action

### Requirement: Group Crowns Management
The admin dashboard MUST provide a `/crowns` page displaying persisted `Crown` records with chat name, artist name, crown holder, playcount, and formatted `updated_at` timestamp, along with filtering and confirmation-gated deletion.

#### Scenario: Viewing and filtering crowns
- **WHEN** an authenticated operator visits `/crowns` and enters an artist or chat filter
- **THEN** the table displays matching `Crown` records ordered by most recently updated, showing chat, artist, holder, playcount, and formatted timestamp

#### Scenario: Clearing crown filters
- **WHEN** an operator clicks Clear on `/crowns`
- **THEN** all filter inputs are cleared and the unfiltered crown list is restored

### Requirement: Chat Members Inspection
The admin dashboard MUST provide a `/members` page displaying persisted `ChatMember` records with chat name, user details, formatted `last_active` timestamp, and `opt_out` status, along with filtering.

#### Scenario: Viewing and filtering chat members
- **WHEN** an authenticated operator visits `/members` and filters by chat or username
- **THEN** the table displays matching `ChatMember` records ordered by most recently active, showing chat name, Telegram username, Last.fm username, formatted `last_active` timestamp, and `opt_out` status

#### Scenario: Clearing chat member filters
- **WHEN** an operator clicks Clear on `/members`
- **THEN** all filter inputs are cleared and the unfiltered chat members list is restored
