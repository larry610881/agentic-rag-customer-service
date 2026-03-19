-- Verify seed data counts
-- Run after seed to confirm all tables have data

\echo '=== Platform Tables ==='
SELECT 'tenants' AS table_name, COUNT(*) AS row_count FROM tenants;
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users;
SELECT 'bots' AS table_name, COUNT(*) AS row_count FROM bots;
SELECT 'knowledge_bases' AS table_name, COUNT(*) AS row_count FROM knowledge_bases;
SELECT 'bot_knowledge_bases' AS table_name, COUNT(*) AS row_count FROM bot_knowledge_bases;
SELECT 'provider_settings' AS table_name, COUNT(*) AS row_count FROM provider_settings;
SELECT 'mcp_server_registrations' AS table_name, COUNT(*) AS row_count FROM mcp_server_registrations;
SELECT 'system_prompt_configs' AS table_name, COUNT(*) AS row_count FROM system_prompt_configs;

\echo '=== Migration Tables ==='
SELECT 'error_events' AS table_name, COUNT(*) AS row_count FROM error_events;
SELECT 'notification_channels' AS table_name, COUNT(*) AS row_count FROM notification_channels;
SELECT 'visitor_profiles' AS table_name, COUNT(*) AS row_count FROM visitor_profiles;
SELECT 'memory_facts' AS table_name, COUNT(*) AS row_count FROM memory_facts;

\echo '=== JoyInKitchen Tables ==='
SELECT 'products' AS table_name, COUNT(*) AS row_count FROM products;
SELECT 'product_categories' AS table_name, COUNT(*) AS row_count FROM product_categories;
SELECT 'product_product_category' AS table_name, COUNT(*) AS row_count FROM product_product_category;
SELECT 'courses' AS table_name, COUNT(*) AS row_count FROM courses;
SELECT 'course_categories' AS table_name, COUNT(*) AS row_count FROM course_categories;
SELECT 'course_stocks' AS table_name, COUNT(*) AS row_count FROM course_stocks;
SELECT 'course_stock_records' AS table_name, COUNT(*) AS row_count FROM course_stock_records;
SELECT 'lectors' AS table_name, COUNT(*) AS row_count FROM lectors;
SELECT 'course_lector' AS table_name, COUNT(*) AS row_count FROM course_lector;

\echo '=== Seed Verification Complete ==='
