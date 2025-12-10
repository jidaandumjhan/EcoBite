# Database Documentation

This directory contains database-related documentation and schema details for the EcoBite application.

## Overview

EcoBite uses **MariaDB** as its relational database management system. The application handles database connections and transactions using the `mariadb` Python connector.

## Database Schema

The database consists of the following primary tables. Note that the schema is defined implicitly through application logic and migration scripts found in the root directory.

### 1. `users`
Stores user account information.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key, Auto Increment |
| `email` | VARCHAR | Unique email address |
| `password_hash` | VARCHAR | Hashed password |
| `role` | VARCHAR | User role (`user`, `business`, `admin`) |

### 2. `posts`
Stores food items shared by users.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key, Auto Increment |
| `user_id` | INTEGER | Foreign Key to `users.id` (Owner) |
| `title` | VARCHAR | Title of the post |
| `description` | TEXT | Detailed description of the food |
| `category` | VARCHAR | Category (e.g., Vegetable, Fruit) |
| `quantity` | VARCHAR | Quantity description (e.g., "5 kg") |
| `estimated_weight_kg`| FLOAT | Estimated weight for impact tracking |
| `dietary_json` | JSON | JSON array of dietary tags |
| `location` | VARCHAR | Pickup location |
| `pickup_window_start`| DATETIME | Start of pickup window |
| `pickup_window_end` | DATETIME | End of pickup window |
| `expires_at` | DATETIME | Expiration timestamp |
| `status` | VARCHAR | Status (`active`, `claimed`, `expired`) |
| `image_url` | VARCHAR | Path to uploaded image |
| `created_at` | TIMESTAMP | Creation timestamp |

### 3. `claims`
Stores requests for food items.

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Primary Key, Auto Increment |
| `post_id` | INTEGER | Foreign Key to `posts.id` |
| `claimer_id` | INTEGER | Foreign Key to `users.id` |
| `message` | TEXT | Message from claimer to owner |
| `requested_quantity` | VARCHAR | Quantity requested |
| `status` | VARCHAR | Status (`pending`, `approved`, `rejected`) |
| `created_at` | TIMESTAMP | Creation timestamp |
| `decided_at` | TIMESTAMP | Timestamp of approval/rejection |

## Utility Scripts

The root directory contains scripts for database management:

-   **`migrate_db.py`**: Handles schema migrations (e.g., adding new columns like `title` or `image_url` to existing tables). Run this script to ensure your database has the latest schema changes.
-   **`inspect_db.py`**: Uses `DESCRIBE` to print the current structure of the `posts` and `claims` tables for debugging purposes.
