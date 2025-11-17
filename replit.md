# Overview

This is a full-featured asynchronous Telegram bot for task management, built with Python and the `aiogram` library. The bot operates via commands (without AI) and uses polling instead of webhooks, making it completely free to run.

The system demonstrates a production-ready implementation with:
- An asynchronous bot on `aiogram 3.22` using polling.
- **Modular architecture v2.0** with separation of concerns.
- A task management system with role-based access (admin/employee).
- PostgreSQL database for storing users and tasks.
- Commands in Russian.
- Free operation without AI costs.
- **Centralized logging** to file and console with rotation.

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
- **Interactive management script** for Ubuntu deployment.

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

The application is built on **Python 3.11 + aiogram 3.22**, utilizing:
- Asynchronous command processing via `asyncio`.
- Polling mode for continuous querying of the Telegram API.
- `MemoryStorage` for the Finite State Machine (FSM).
- Automatic handling of updates from Telegram.
- **Modular Router-based architecture** (aiogram 3.x best practices).

## Modular Structure (v2.0)

The codebase is organized into clean, testable modules:

```
app/
├── __init__.py                 # Package initialization
├── main.py                     # Bot initialization & router registration
├── config.py                   # Configuration constants
├── logging_config.py           # Centralized logging setup
├── database.py                 # PostgreSQL connection & schema init
├── states.py                   # FSM state definitions
├── keyboards/                  # Inline keyboard builders
│   ├── main_menu.py
│   ├── task_keyboards.py
│   └── user_keyboards.py
├── services/                   # Business logic layer
│   ├── users.py              # User authorization & management
│   └── tasks.py              # Task operations (future)
└── handlers/                   # Event handlers (routers)
    ├── __init__.py           # Router definitions
    ├── core.py               # Core commands & menus
    ├── statuses.py           # Task status updates
    └── photos.py             # Photo attachment handling

bot.py                          # Entry point
START_BOT.sh                    # Interactive management menu
logs/                           # Rotating log files
```

### Module Responsibilities

**app/main.py**: Bot & dispatcher initialization, router registration, startup/shutdown hooks.

**app/config.py**: All configuration constants (BOT_TOKEN, DATABASE_URL, status/priority mappings).

**app/logging_config.py**: Rotating file handler + console output, structured logging format.

**app/database.py**: Connection pool management, schema initialization (CREATE TABLE IF NOT EXISTS).

**app/keyboards/**: Reusable inline keyboard factories, isolated from handler logic.

**app/services/**: Business logic and database operations, used by handlers.

**app/handlers/**: Command & callback handlers organized by domain:
- `core.py`: /start, help, task lists, task creation, deletion, user management
- `statuses.py`: Task status transitions, completion flow, reopening tasks
- `photos.py`: Photo uploads for task creation and completion

## Database Layer

**PostgreSQL with psycopg2** is used for data management:
- **Schema Design**: Three main tables (`users`, `tasks`, `allowed_users`) with enum types for roles, priorities, and statuses.
- **Relations**: Foreign key relationships between `users` and `tasks` (assigned_to_id, created_by_id).
- **Connection**: Synchronous `psycopg2` driver connecting via `DATABASE_URL`.
- **Initialization**: Automatic schema creation via `app.database.init_database()`.
- **Key Entities**:
    - **Users**: Telegram ID (unique), username, role (admin/employee), timestamps.
    - **Tasks**: Title, description, priority, status, due date, assignment tracking, `task_photo_file_id`, `photo_file_id` (for completion), `completion_comment`.
    - **Allowed Users**: Username (unique), role, `added_by_id`, `created_at` (whitelist for authorization).

## Bot Architecture

**Aiogram 3 Router Pattern**:
- Three routers (`core_router`, `statuses_router`, `photos_router`) registered in `app.main`.
- Handlers use `@router.message` and `@router.callback_query` decorators.
- No circular dependencies: handlers access bot via `callback.message.bot` or `message.bot`.
- Command filters for command-specific processing.
- Asynchronous functions process requests.
- Access rights validation via `app.services.users.get_or_create_user()`.

**Handler Pattern**: Each command has an asynchronous handler that:
1. Retrieves or creates a user via service layer.
2. Checks access rights (whitelist + role).
3. Performs the database operation.
4. Sends a response via the Telegram Bot API.

## Logging System

**Centralized logging** via `app.logging_config`:
- **File Handler**: Rotating logs in `logs/bot.log` (10MB per file, 5 backups).
- **Console Handler**: Real-time output for development.
- **Format**: `YYYY-MM-DD HH:MM:SS - module - level - message`.
- **Levels**: DEBUG for file, INFO for console.
- All modules use `get_logger(__name__)` for consistent logging.

## Deployment & Management

**START_BOT.sh** - Interactive menu for bot management:
- Start/stop/restart bot manually.
- View logs (last 50 lines).
- Check bot status.
- **Ubuntu Server Integration**:
  - Install as systemd service.
  - Enable auto-start on boot.
  - Manage service (start/stop/status).
  - View systemd logs via journalctl.

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
- **Why Modular Architecture**: Improved testability, maintainability, separation of concerns, easier debugging.
- **Why Router Pattern**: Aligns with aiogram 3.x best practices, prevents circular imports, enables modular composition.

## UI/UX Decisions

- **Interactive Inline Buttons**: All user interactions are managed through inline buttons within Telegram for a streamlined experience.
- **Role-Based Access**: Clear distinction between admin and employee functionalities to manage permissions effectively.
- **Task Photo Integration**: Allows visual context for tasks, improving clarity and communication.
- **"Open Task" Button**: Provides a quick navigation shortcut from notifications to task details.
- **Comprehensive Logging**: All operations logged with emoji indicators for easy debugging and monitoring.

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

# Recent Changes (2025-11-17)

## Major Refactoring: Modular Architecture v2.0

- **Separated monolithic bot.py (2255 lines) into modular structure**:
  - Core configuration and logging modules
  - Keyboard factories separated from handlers
  - Business logic extracted into services
  - Handlers split by domain (core/statuses/photos)
  
- **Fixed circular dependency**: Removed `from app.main import bot` imports, handlers now use dependency injection pattern.

- **Added comprehensive logging**: All modules log to both file (`logs/bot.log`) and console with rotation.

- **Created interactive management script**: `START_BOT.sh` with menu for Ubuntu server deployment and systemd service management.

- **Improved maintainability**: Each module has clear responsibility, easier to test and extend.

## Bug Fixes & UX Improvements (2025-11-17 Evening)

- **Fixed critical bug**: Added missing FSM state `asking_for_task_photo` in `CreateTaskStates`, resolving AttributeError during task creation.
  
- **Fixed database enum**: Added missing `partially_completed` status to PostgreSQL enum type `task_status`.

- **Fixed message editing error**: Added error handling for edit_text operations with fallback to delete+answer pattern when editing messages with photos.

- **Fixed notification logic**: Removed inconsistent check that prevented self-notifications on task completion. Now matches creation behavior where admins receive all notifications including self-assigned tasks.

- **Enhanced UX**: Added "📂 Открыть задачу" button to all admin notifications (task completion with/without photo).

- **Improved navigation**: Added "🔙 Главное меню" button to ALL FSM keyboards:
  - Task creation flow (title, description, priority, due date, assignee, photo)
  - Task completion flow (comment, photo upload)
  - User management flow (add admin, add employee)
  - All cancel/skip keyboards
  
This ensures users can exit to main menu from any point in the workflow without getting stuck.
