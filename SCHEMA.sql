-- ============================================================
-- Helpdesk & Client Management System — MariaDB Schema
-- Multi-organization B2B helpdesk
-- Engine: InnoDB, charset utf8mb4 (full Unicode incl. Vietnamese)
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- Organizations (Đơn vị khách hàng)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS organizations (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200)  NOT NULL,
    code          VARCHAR(50)   NOT NULL UNIQUE,          -- e.g. CTY-A
    contact_email VARCHAR(255),
    phone         VARCHAR(50),
    status        ENUM('active','inactive','suspended') NOT NULL DEFAULT 'active',
    notes         TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_org_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Users (Admin / Staff / Customer)
-- A user belongs to an organization (staff/admin can belong to the
-- internal/provider org; customers belong to their client org).
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id        BIGINT NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(200) NOT NULL,
    role          ENUM('admin','staff','customer') NOT NULL DEFAULT 'customer',
    phone         VARCHAR(50),
    is_active     TINYINT(1) NOT NULL DEFAULT 1,
    last_login_at DATETIME,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_org FOREIGN KEY (org_id) REFERENCES organizations(id),
    INDEX idx_user_role (role),
    INDEX idx_user_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Teams (for staff grouping / routing)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teams (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    description VARCHAR(255),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS team_members (
    team_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY (team_id, user_id),
    CONSTRAINT fk_tm_team FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
    CONSTRAINT fk_tm_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Optional: which orgs a staff member is responsible for
CREATE TABLE IF NOT EXISTS staff_org_assignments (
    user_id BIGINT NOT NULL,
    org_id  BIGINT NOT NULL,
    PRIMARY KEY (user_id, org_id),
    CONSTRAINT fk_soa_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_soa_org  FOREIGN KEY (org_id)  REFERENCES organizations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Service categories
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS service_categories (
    id   BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Services (Gói dịch vụ) — SaaS subscription or Hosting plan
-- Belongs to an organization.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS services (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id        BIGINT NOT NULL,
    category_id   BIGINT,
    type          ENUM('saas','hosting','other') NOT NULL DEFAULT 'saas',
    name          VARCHAR(200) NOT NULL,            -- e.g. "Business Pro"
    domain        VARCHAR(255),                     -- for hosting
    status        ENUM('active','inactive','cancelled','past_due') NOT NULL DEFAULT 'active',
    start_date    DATE,
    expiry_date   DATE,                             -- next renewal / expiry
    disk_usage    VARCHAR(50),                      -- free text e.g. "30GB / 50GB"
    monthly_cost  DECIMAL(15,2) DEFAULT 0,
    billing_cycle ENUM('monthly','quarterly','yearly') DEFAULT 'monthly',
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_service_org FOREIGN KEY (org_id) REFERENCES organizations(id),
    CONSTRAINT fk_service_cat FOREIGN KEY (category_id) REFERENCES service_categories(id),
    INDEX idx_service_org (org_id),
    INDEX idx_service_status (status),
    INDEX idx_service_expiry (expiry_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- SLA policies (per priority)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sla_policies (
    id                 BIGINT AUTO_INCREMENT PRIMARY KEY,
    priority           ENUM('Low','Medium','High','Urgent') NOT NULL UNIQUE,
    response_hours     DECIMAL(5,2) NOT NULL,   -- first response target (hours; 0.25 = 15 min)
    resolution_hours   DECIMAL(5,2) NOT NULL,   -- resolution target (hours)
    created_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Tickets (trung tâm) — always belongs to an org + a service
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    org_id        BIGINT NOT NULL,                  -- ĐƠN VỊ (required)
    service_id    BIGINT,                           -- GÓI DỊCH VỤ (required at create; nullable for safety)
    subject       VARCHAR(300) NOT NULL,
    description   TEXT,
    status        ENUM('Open','In Progress','Waiting','Resolved','Closed')
                    NOT NULL DEFAULT 'Open',         -- DEFAULT Open (fixes empty-status bug)
    priority      ENUM('Low','Medium','High','Urgent') NOT NULL DEFAULT 'Medium',
    ticket_type   ENUM('Bug','Incident','Question','Unspecified',
                       'Service SaaS','Service Hosting','Renewal')
                    NOT NULL DEFAULT 'Unspecified',
    source        ENUM('portal','email','phone','manual') NOT NULL DEFAULT 'portal',
    raised_by     BIGINT,                           -- user who raised it
    raised_by_email VARCHAR(255),                   -- raw email (for unknown senders via email piping)
    assignee_id   BIGINT,                           -- agent
    team_id       BIGINT,
    -- SLA computed timestamps
    response_by   DATETIME,
    resolution_by DATETIME,
    first_responded_at DATETIME,
    resolved_at   DATETIME,
    closed_at     DATETIME,
    sla_state     ENUM('green','amber','red','breached') DEFAULT 'green',
    is_deleted    TINYINT(1) NOT NULL DEFAULT 0,     -- soft delete
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ticket_org      FOREIGN KEY (org_id)      REFERENCES organizations(id),
    CONSTRAINT fk_ticket_service  FOREIGN KEY (service_id)  REFERENCES services(id),
    CONSTRAINT fk_ticket_raiser   FOREIGN KEY (raised_by)   REFERENCES users(id),
    CONSTRAINT fk_ticket_assignee FOREIGN KEY (assignee_id) REFERENCES users(id),
    CONSTRAINT fk_ticket_team     FOREIGN KEY (team_id)     REFERENCES teams(id),
    INDEX idx_ticket_org (org_id),
    INDEX idx_ticket_status (status),
    INDEX idx_ticket_priority (priority),
    INDEX idx_ticket_assignee (assignee_id),
    INDEX idx_ticket_created (created_at),
    FULLTEXT INDEX ft_ticket_subject (subject)        -- for similar-ticket search
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Ticket replies (conversation thread)
-- is_internal = staff-only note (never shown to customer)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_replies (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticket_id   BIGINT NOT NULL,
    author_id   BIGINT,
    author_email VARCHAR(255),
    content     TEXT NOT NULL,
    is_internal TINYINT(1) NOT NULL DEFAULT 0,        -- internal note vs customer-visible
    source      ENUM('portal','email','manual') NOT NULL DEFAULT 'portal',
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_reply_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    CONSTRAINT fk_reply_author FOREIGN KEY (author_id) REFERENCES users(id),
    INDEX idx_reply_ticket (ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Ticket activities (audit log: status changes, assignment, etc.)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ticket_activities (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    ticket_id  BIGINT NOT NULL,
    actor_id   BIGINT,
    action     VARCHAR(100) NOT NULL,                 -- e.g. 'status_change','assigned','created'
    from_value VARCHAR(100),
    to_value   VARCHAR(100),
    detail     VARCHAR(255),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_act_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE,
    CONSTRAINT fk_act_actor  FOREIGN KEY (actor_id)  REFERENCES users(id),
    INDEX idx_act_ticket (ticket_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Notifications
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS notifications (
    id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT NOT NULL,
    title      VARCHAR(255) NOT NULL,
    content    TEXT,
    type       ENUM('info','sla','assignment','reply','expiry') NOT NULL DEFAULT 'info',
    ref_ticket_id BIGINT,
    is_read    TINYINT(1) NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notif_user (user_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ------------------------------------------------------------
-- Email piping log (audit of processed emails)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS email_log (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    message_id   VARCHAR(255) UNIQUE,                  -- IMAP Message-ID to avoid duplicates
    from_email   VARCHAR(255),
    subject      VARCHAR(300),
    ticket_id    BIGINT,                               -- created/updated ticket
    action       ENUM('created','appended','skipped','error') NOT NULL,
    detail       VARCHAR(255),
    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_email_ticket FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    INDEX idx_email_from (from_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- Seed data (defaults)
-- ============================================================

-- Default SLA policies (hours)
INSERT INTO sla_policies (priority, response_hours, resolution_hours) VALUES
    ('Urgent', 0.25, 2),
    ('High',   1,    8),
    ('Medium', 4,    24),
    ('Low',    8,    72)
ON DUPLICATE KEY UPDATE response_hours=VALUES(response_hours);

-- Default service categories
INSERT INTO service_categories (name, slug) VALUES
    ('SaaS Subscription', 'saas'),
    ('Web Hosting', 'hosting'),
    ('Domain', 'domain'),
    ('Support Package', 'support')
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Provider organization (internal — where admin/staff live)
INSERT INTO organizations (name, code, contact_email, status) VALUES
    ('OSD Provider', 'PROVIDER', 'admin@osd.vn', 'active')
ON DUPLICATE KEY UPDATE name=VALUES(name);
