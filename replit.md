# Overview

This is a full-featured asynchronous Telegram bot for task management, built with Python and the `aiogram` library. The bot operates via commands (without AI) and uses polling instead of webhooks, making it completely free to run.

The system demonstrates a production-ready implementation with:
- An asynchronous bot on `aiogram 3.22` using polling.
- A task management system with role-based access (admin/employee).
- PostgreSQL database for storing users and tasks.
- Commands in Russian.
- Free operation without AI costs.

Key capabilities include:
- Interactive inline buttons for all commands.
- Whitelist authorization system by username.
- Access rights validation (admin vs. employee).
- FSM for task creation and user management.
- Error handling and data validation.
- Ability for admins to attach photos to tasks.
- Photos included in notifications when available.
- "Open Task" button in all notifications for quick access.
- User lists displayed when removing admins/employees.

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

The application is built on **Python 3.11 + aiogram 3.22**, utilizing:
- Asynchronous command processing via `asyncio`.
- Polling mode for continuous querying of the Telegram API.
- `MemoryStorage` for the Finite State Machine (FSM).
- Automatic handling of updates from Telegram.

## Database Layer

**PostgreSQL with psycopg2** is used for data management:
- **Schema Design**: Three main tables (`users`, `tasks`, `allowed_users`) with enum types for roles, priorities, and statuses.
- **Relations**: Foreign key relationships between `users` and `tasks` (assigned_to_id, created_by_id).
- **Connection**: Synchronous `psycopg2` driver connecting via `DATABASE_URL`.
- **Key Entities**:
    - **Users**: Telegram ID (unique), username, role (admin/employee), timestamps.
    - **Tasks**: Title, description, priority, status, due date, assignment tracking, `task_photo_file_id`, `photo_file_id` (for completion), `completion_comment`.
    - **Allowed Users**: Username (unique), role, `added_by_id`, `created_at` (whitelist for authorization).

## Bot Architecture

**Aiogram Handlers** in `bot.py` manage Telegram commands:
- `@dp.message` decorators register handlers.
- Command filters for command-specific processing.
- Asynchronous functions process requests.
- Direct interaction with PostgreSQL via `psycopg2`.
- Access rights validation implemented at the handler level.

**Handler Pattern**: Each command has an asynchronous handler that:
1. Retrieves or creates a user in the database.
2. Checks access rights.
3. Performs the database operation.
4. Sends a response via the Telegram Bot API.

## Polling vs. Webhook

The current implementation uses **Polling** due to its advantages:
- Instant launch without needing to publish the Replit application.
- No HTTPS certificate required.
- Simpler setup and debugging.
- The bot continuously queries the Telegram API for new messages.

## Design Decisions

- **Why Python + aiogram**: Ease of development, excellent documentation, native asynchronous capabilities, large community.
- **Why Polling**: Simpler setup, works without deployment, ideal for development and testing.
- **Why PostgreSQL**: Reliable relational database with transaction support, foreign keys, and complex queries.
- **Why no AI**: Ensures completely free operation, predictable behavior, and fast command processing.

## UI/UX Decisions

- **Interactive Inline Buttons**: All user interactions are managed through inline buttons within Telegram for a streamlined experience.
- **Role-Based Access**: Clear distinction between admin and employee functionalities to manage permissions effectively.
- **Task Photo Integration**: Allows visual context for tasks, improving clarity and communication.
- **"Open Task" Button**: Provides a quick navigation shortcut from notifications to task details.

# External Dependencies

## AI/LLM Services
- **None**: The bot operates without AI services.

## Database & Storage
- **PostgreSQL**: Primary database (connected via `DATABASE_URL`).
- **psycopg2-binary**: Synchronous PostgreSQL driver (v2.9.11).

## Telegram Integration
- **aiogram**: Asynchronous library for Telegram Bot API (v3.22.0).
- **aiohttp**: HTTP client for asynchronous requests (v3.12.15).
- **Telegram Bot API**: Interaction via polling.

## Utilities
- **python-dotenv**: For loading environment variables (v1.2.1).
- **typing-extensions**: For extended type support (v4.15.0).