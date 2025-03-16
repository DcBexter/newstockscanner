-- Create exchanges table
CREATE TABLE exchanges (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    code VARCHAR NOT NULL UNIQUE,
    url VARCHAR NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create stock_listings table
CREATE TABLE stock_listings (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    symbol VARCHAR NOT NULL,
    listing_date TIMESTAMP NOT NULL,
    lot_size INTEGER,
    exchange_id INTEGER REFERENCES exchanges(id),
    status VARCHAR,
    security_type VARCHAR(50) DEFAULT 'Equity',
    remarks TEXT,
    url VARCHAR(255),
    listing_detail_url VARCHAR(255),
    notified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create notification_logs table
CREATE TABLE notification_logs (
    id SERIAL PRIMARY KEY,
    notification_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error TEXT,
    notification_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial exchange data
INSERT INTO exchanges (name, code, url) VALUES 
('Hong Kong Stock Exchange', 'HKEX', 'https://www.hkex.com.hk'); 