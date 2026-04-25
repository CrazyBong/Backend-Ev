"""initial_schema

Revision ID: 42b070653d86
Revises: 
Create Date: 2026-04-25 18:19:17.779367

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42b070653d86'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")  # for text search

    # ENUMS
    op.execute("""
        CREATE TYPE user_role AS ENUM ('user', 'station_admin', 'super_admin');
        CREATE TYPE slot_status AS ENUM ('AVAILABLE', 'BOOKED', 'IN_USE', 'LOCKED', 'OFFLINE');
        CREATE TYPE booking_status AS ENUM (
            'PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE', 'COMPLETED',
            'CANCELLED_BY_USER', 'CANCELLED_BY_ADMIN', 'NO_SHOW', 'REFUND_PENDING'
        );
        CREATE TYPE payment_status AS ENUM (
            'CREATED', 'PENDING_WEBHOOK', 'SUCCESS', 'FAILED', 'REFUNDED', 'PARTIALLY_REFUNDED'
        );
        CREATE TYPE charger_type AS ENUM ('CCS2', 'CHAdeMO', 'TYPE2', 'BHARAT_AC', 'BHARAT_DC');
        CREATE TYPE charging_network AS ENUM (
            'TATA_POWER', 'CHARGE_ZONE', 'ATHER_GRID', 'STATIQ', 'BPCL_PULSE', 'EESL', 'INDEPENDENT'
        );
        CREATE TYPE notification_type AS ENUM (
            'BOOKING_CONFIRMED', 'BOOKING_REMINDER', 'BOOKING_CANCELLED',
            'SLOT_AVAILABLE', 'PAYMENT_SUCCESS', 'PAYMENT_FAILED', 'REFUND_INITIATED'
        );
    """)

    # USERS
    op.execute("""
        CREATE TABLE users (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone            VARCHAR(15)  NOT NULL UNIQUE,
            name             VARCHAR(100),
            email            VARCHAR(255) UNIQUE,
            role             user_role    NOT NULL DEFAULT 'user',
            vehicle_type     VARCHAR(100),
            preferred_connector charger_type,
            expo_push_token  VARCHAR(255),
            is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
        )
    """)

    # STATIONS
    op.execute("""
        CREATE TABLE stations (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name             VARCHAR(200)  NOT NULL,
            network          charging_network NOT NULL,
            location         GEOGRAPHY(POINT, 4326) NOT NULL,
            address          JSONB         NOT NULL,
            operating_hours  JSONB         NOT NULL,
            amenities        TEXT[]        DEFAULT '{}',
            price_per_unit   DECIMAL(10,2),
            price_per_hour   DECIMAL(10,2),
            is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
            total_slots      INTEGER       NOT NULL DEFAULT 0,
            available_slots  INTEGER       NOT NULL DEFAULT 0,
            avg_rating       DECIMAL(3,2)  DEFAULT 0.00,
            total_reviews    INTEGER       DEFAULT 0,
            last_heartbeat   TIMESTAMPTZ,
            admin_user_id    UUID          REFERENCES users(id) ON DELETE SET NULL,
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            -- OCPP-ready fields
            ocpp_station_id  VARCHAR(50) UNIQUE,  -- EVSE ID for future hardware

            CONSTRAINT chk_available_lte_total CHECK (available_slots <= total_slots),
            CONSTRAINT chk_available_gte_zero  CHECK (available_slots >= 0),
            CONSTRAINT chk_rating_range        CHECK (avg_rating BETWEEN 0 AND 5)
        )
    """)

    # SLOTS
    op.execute("""
        CREATE TABLE slots (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            station_id       UUID          NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            slot_number      INTEGER       NOT NULL,
            charger_type     charger_type  NOT NULL,
            power_kw         DECIMAL(6,1)  NOT NULL,
            status           slot_status   NOT NULL DEFAULT 'AVAILABLE',
            fault_code       VARCHAR(50),
            locked_by_user   UUID          REFERENCES users(id) ON DELETE SET NULL,
            locked_until     TIMESTAMPTZ,
            ocpp_connector_id INTEGER,     -- OCPP-ready
            created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            UNIQUE (station_id, slot_number),
            CONSTRAINT chk_lock_consistency CHECK (
                (locked_until IS NULL AND locked_by_user IS NULL) OR
                (locked_until IS NOT NULL AND locked_by_user IS NOT NULL)
            )
        )
    """)

    # BOOKINGS
    op.execute("""
        CREATE TABLE bookings (
            id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID          NOT NULL REFERENCES users(id),
            slot_id           UUID          NOT NULL REFERENCES slots(id),
            station_id        UUID          NOT NULL REFERENCES stations(id),
            status            booking_status NOT NULL DEFAULT 'PENDING_PAYMENT',
            scheduled_start   TIMESTAMPTZ   NOT NULL,
            scheduled_end     TIMESTAMPTZ   NOT NULL,
            actual_start      TIMESTAMPTZ,
            actual_end        TIMESTAMPTZ,
            amount            DECIMAL(10,2) NOT NULL,
            energy_consumed_kwh DECIMAL(8,2),
            qr_code           VARCHAR(500),
            cancellation_reason TEXT,
            idempotency_key   VARCHAR(36)   NOT NULL UNIQUE,
            created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            CONSTRAINT chk_time_order CHECK (scheduled_end > scheduled_start),
            CONSTRAINT chk_future_booking CHECK (scheduled_start >= created_at)
        )
    """)

    # PAYMENTS
    op.execute("""
        CREATE TABLE payments (
            id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            booking_id            UUID          NOT NULL REFERENCES bookings(id) UNIQUE,
            user_id               UUID          NOT NULL REFERENCES users(id),
            razorpay_order_id     VARCHAR(100)  NOT NULL UNIQUE,
            razorpay_payment_id   VARCHAR(100)  UNIQUE,
            status                payment_status NOT NULL DEFAULT 'CREATED',
            amount                DECIMAL(10,2) NOT NULL,
            refund_amount         DECIMAL(10,2) DEFAULT 0.00,
            razorpay_refund_id    VARCHAR(100),
            webhook_verified      BOOLEAN       DEFAULT FALSE,
            webhook_received_at   TIMESTAMPTZ,
            created_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at            TIMESTAMPTZ   NOT NULL DEFAULT NOW()
        )
    """)

    # REVIEWS
    op.execute("""
        CREATE TABLE reviews (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     UUID          NOT NULL REFERENCES users(id),
            station_id  UUID          NOT NULL REFERENCES stations(id),
            booking_id  UUID          UNIQUE REFERENCES bookings(id),
            rating      SMALLINT      NOT NULL,
            comment     TEXT,
            created_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
            updated_at  TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

            UNIQUE (user_id, station_id, booking_id),
            CONSTRAINT chk_rating_1_to_5 CHECK (rating BETWEEN 1 AND 5)
        )
    """)

    # NOTIFICATIONS (in-app)
    op.execute("""
        CREATE TABLE notifications (
            id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      UUID              NOT NULL REFERENCES users(id),
            type         notification_type NOT NULL,
            title        VARCHAR(200)      NOT NULL,
            body         TEXT              NOT NULL,
            data         JSONB             DEFAULT '{}',
            is_read      BOOLEAN           NOT NULL DEFAULT FALSE,
            created_at   TIMESTAMPTZ       NOT NULL DEFAULT NOW()
        )
    """)

    # OTP (temp table — high write, fast expiry)
    op.execute("""
        CREATE TABLE otp_records (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            phone       VARCHAR(15) NOT NULL,
            otp_hash    VARCHAR(64) NOT NULL,   -- bcrypt hash of OTP
            attempts    SMALLINT    NOT NULL DEFAULT 0,
            expires_at  TIMESTAMPTZ NOT NULL,
            used        BOOLEAN     NOT NULL DEFAULT FALSE,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # DEMAND PREDICTIONS (AI output cache)
    op.execute("""
        CREATE TABLE demand_predictions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            station_id  UUID         REFERENCES stations(id),
            predicted_for DATE        NOT NULL,
            hour        SMALLINT     NOT NULL,
            predicted_load DECIMAL(5,2) NOT NULL,  -- 0.0 to 1.0
            confidence  DECIMAL(5,2),
            model_version VARCHAR(20),
            created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            UNIQUE (station_id, predicted_for, hour),
            CONSTRAINT chk_predicted_load_range CHECK (predicted_load BETWEEN 0.0 AND 1.0)
        )
    """)

    # JWT blacklist (for logout)
    op.execute("""
        CREATE TABLE jwt_blacklist (
            jti        VARCHAR(36) PRIMARY KEY,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    # Create Indexes
    op.execute("CREATE INDEX idx_stations_location ON stations USING GIST (location)")
    op.execute("CREATE INDEX idx_stations_network ON stations (network)")
    op.execute("CREATE INDEX idx_stations_active ON stations (is_active) WHERE is_active = TRUE")

    # Slots
    op.execute("CREATE INDEX idx_slots_station_id ON slots (station_id)")
    op.execute("CREATE INDEX idx_slots_status ON slots (status)")
    op.execute("CREATE INDEX idx_slots_locked_until ON slots (locked_until) WHERE locked_until IS NOT NULL")

    # Bookings
    op.execute("CREATE INDEX idx_bookings_user_id ON bookings (user_id)")
    op.execute("CREATE INDEX idx_bookings_slot_id ON bookings (slot_id)")
    op.execute("CREATE INDEX idx_bookings_station_id ON bookings (station_id)")
    op.execute("CREATE INDEX idx_bookings_status ON bookings (status)")
    op.execute("CREATE INDEX idx_bookings_scheduled_start ON bookings (scheduled_start)")
    op.execute("""
        CREATE INDEX idx_bookings_active_window
        ON bookings (slot_id, scheduled_start, scheduled_end)
        WHERE status IN ('PENDING_PAYMENT', 'CONFIRMED', 'ACTIVE')
    """)

    # Notifications
    op.execute("CREATE INDEX idx_notifications_user_unread ON notifications (user_id) WHERE is_read = FALSE")

    # OTP
    op.execute("CREATE UNIQUE INDEX idx_otp_phone_active ON otp_records (phone) WHERE used = FALSE")

    # JWT blacklist
    op.execute("CREATE INDEX idx_jwt_blacklist_expires ON jwt_blacklist (expires_at)")

    # TRIGGERS
    op.execute("""
        -- Auto-update stations.available_slots when any slot status changes
        CREATE OR REPLACE FUNCTION update_station_available_slots()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE stations
            SET available_slots = (
                SELECT COUNT(*) FROM slots
                WHERE station_id = COALESCE(NEW.station_id, OLD.station_id)
                AND status = 'AVAILABLE'
            ),
            updated_at = NOW()
            WHERE id = COALESCE(NEW.station_id, OLD.station_id);
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_slot_status_change
            AFTER INSERT OR UPDATE OF status OR DELETE ON slots
            FOR EACH ROW EXECUTE FUNCTION update_station_available_slots();

        -- Auto-update station avg_rating when review added
        CREATE OR REPLACE FUNCTION update_station_rating()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE stations
            SET avg_rating = (
                SELECT ROUND(AVG(rating)::NUMERIC, 2)
                FROM reviews WHERE station_id = NEW.station_id
            ),
            total_reviews = (
                SELECT COUNT(*) FROM reviews WHERE station_id = NEW.station_id
            ),
            updated_at = NOW()
            WHERE id = NEW.station_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_review_change
            AFTER INSERT OR UPDATE OR DELETE ON reviews
            FOR EACH ROW EXECUTE FUNCTION update_station_rating();

        -- Clean up expired OTPs (called by cron job)
        CREATE OR REPLACE FUNCTION cleanup_expired_otps()
        RETURNS void AS $$
        BEGIN
            DELETE FROM otp_records WHERE expires_at < NOW() OR used = TRUE;
        END;
        $$ LANGUAGE plpgsql;

        -- Clean up expired JWT blacklist entries
        CREATE OR REPLACE FUNCTION cleanup_jwt_blacklist()
        RETURNS void AS $$
        BEGIN
            DELETE FROM jwt_blacklist WHERE expires_at < NOW();
        END;
        $$ LANGUAGE plpgsql;
    """)


def downgrade():
    # Drop Triggers
    op.execute("DROP TRIGGER IF EXISTS trg_review_change ON reviews")
    op.execute("DROP FUNCTION IF EXISTS update_station_rating")
    op.execute("DROP TRIGGER IF EXISTS trg_slot_status_change ON slots")
    op.execute("DROP FUNCTION IF EXISTS update_station_available_slots")
    op.execute("DROP FUNCTION IF EXISTS cleanup_expired_otps")
    op.execute("DROP FUNCTION IF EXISTS cleanup_jwt_blacklist")

    op.execute("DROP TABLE IF EXISTS jwt_blacklist")
    op.execute("DROP TABLE IF EXISTS demand_predictions")
    op.execute("DROP TABLE IF EXISTS otp_records")
    op.execute("DROP TABLE IF EXISTS notifications")
    op.execute("DROP TABLE IF EXISTS reviews")
    op.execute("DROP TABLE IF EXISTS payments")
    op.execute("DROP TABLE IF EXISTS bookings")
    op.execute("DROP TABLE IF EXISTS slots")
    op.execute("DROP TABLE IF EXISTS stations")
    op.execute("DROP TABLE IF EXISTS users")
    
    # Drop Enums
    op.execute("DROP TYPE IF EXISTS notification_type")
    op.execute("DROP TYPE IF EXISTS charging_network")
    op.execute("DROP TYPE IF EXISTS charger_type")
    op.execute("DROP TYPE IF EXISTS payment_status")
    op.execute("DROP TYPE IF EXISTS booking_status")
    op.execute("DROP TYPE IF EXISTS slot_status")
    op.execute("DROP TYPE IF EXISTS user_role")

    # Drop Extensions
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS postgis")
