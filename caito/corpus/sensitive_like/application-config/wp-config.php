<?php
/**
 * WordPress on Windows/IIS: C:\inetpub\wwwroot\blog\wp-config.php
 * DB creds + auth salts in cleartext.
 */
define( 'DB_NAME', 'wp_blog' );
define( 'DB_USER', 'wp_admin' );
define( 'DB_PASSWORD', 'Wp-Bl0g-DB-2026!' );
define( 'DB_HOST', 'mysql01.example.com' );
define( 'DB_CHARSET', 'utf8mb4' );
define( 'DB_COLLATE', '' );

define( 'AUTH_KEY',         'x9F!2aB#cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5aB6cD7eF8gH9iJ0kL' );
define( 'SECURE_AUTH_KEY',  'q1W2e3R4t5Y6u7I8o9P0a1S2d3F4g5H6j7K8l9Z0x1C2v3B4n5M6q7W8e9R0' );
define( 'LOGGED_IN_KEY',    'Z0x1C2v3B4n5M6q7W8e9R0t5Y6u7I8o9P0a1S2d3F4g5H6j7K8l9x9F!2aB#' );
define( 'NONCE_KEY',        'm9N8b7V6c5X4z3L2k1J0h9G8f7D6s5A4p3O2i1U0y9T8r7E6w5Q4a3Z2x1C0' );
define( 'AUTH_SALT',        'aB6cD7eF8gH9iJ0kLx9F!2aB#cD4eF5gH6iJ7kL8mN9oP0qR1sT2uV3wX4yZ5' );
define( 'SECURE_AUTH_SALT', 'p3O2i1U0y9T8r7E6w5Q4a3Z2x1C0m9N8b7V6c5X4z3L2k1J0h9G8f7D6s5A4' );
define( 'LOGGED_IN_SALT',   'g5H6j7K8l9Z0x1C2v3B4n5M6q7W8e9R0t5Y6u7I8o9P0a1S2d3F4x9F!2aB#c' );
define( 'NONCE_SALT',       's5A4p3O2i1U0y9T8r7E6w5Q4a3Z2x1C0m9N8b7V6c5X4z3L2k1J0h9G8f7D6' );

$table_prefix = 'wp_';
define( 'WP_DEBUG', false );

if ( ! defined( 'ABSPATH' ) ) {
	define( 'ABSPATH', __DIR__ . '/' );
}
require_once ABSPATH . 'wp-settings.php';
