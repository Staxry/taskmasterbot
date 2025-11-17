# Overview

This project is a full-featured asynchronous Telegram bot designed for task management. Built with Python and the `aiogram` library, it operates via commands using polling, ensuring free operation without AI costs. The system offers a robust, production-ready implementation with a modular architecture, role-based access for task management (admin/employee), and utilizes **SQLite** for local data storage. Its core capabilities include interactive inline buttons for all commands, a whitelist authorization system, FSM for task and user management, error handling, task photos, automated deadline notifications (24h/3h reminders and overdue alerts), advanced statistics with Excel export, pagination, search, and **full timezone support with precise time selection**. The project aims to provide an efficient and cost-effective solution for team task coordination with proactive deadline management and accurate time tracking in the Kaliningrad timezone (UTC+2).

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

The application is developed with **Python 3.11 and aiogram 3.22**, leveraging `asyncio` for asynchronous command processing and operating in polling mode for continuous Telegram API interaction. It uses `MemoryStorage` for the Finite State Machine (FSM) and adheres to `aiogram 3.x` best practices with a modular, router-based architecture. The system includes **pytz** for comprehensive timezone support, ensuring all timestamps are stored and displayed correctly in the Kaliningrad timezone (Europe/Kaliningrad UTC+2).

## Modular Structure (v2.0)

The codebase is organized for clarity and maintainability:
- `app/main.py`: Bot initialization, router registration, and notification scheduler integration.
- `app/config.py`: Centralized configuration constants.
- `app/logging_config.py`: Centralized logging setup.
- `app/database.py`: PostgreSQL connection and schema management.
- `app/states.py`: FSM state definitions.
- `app/keyboards/`: Reusable inline keyboard factories.
- `app/services/`: Business logic for users, tasks, notifications, and statistics.
- `app/handlers/`: Event handlers organized by domain (core, statuses, photos).
- `bot.py`: Entry point.
- `START_BOT.sh`: Interactive management script for deployment.
- `requirements_deploy.txt`: Complete production dependencies for server deployment.

## Database Layer

**SQLite3** manages data (файловая база данных), featuring:
- A schema with `users`, `tasks`, `allowed_users`, and `task_notifications` tables.
- Enum types for roles, priorities, and statuses.
- Foreign key relationships between users and tasks.
- Automatic schema initialization on startup.
- Key entities:
    - **Users**: Telegram ID, username, role, timestamps.
    - **Tasks**: Title, description, priority, status, due date (TIMESTAMP), assignment, photo file IDs, completion comment.
    - **Allowed Users**: Whitelist for authorization by username and role.
    - **Task Notifications**: Tracking sent notifications (task_id, notification_type, sent_at) to prevent duplicates.

## Bot Architecture

Utilizes the **Aiogram 3 Router Pattern** with `core_router`, `statuses_router`, and `photos_router` registered in `app.main`. Handlers are asynchronous and use decorators. Access rights are validated via the service layer. Each command handler retrieves/creates a user, checks access, performs database operations, and sends a Telegram API response.

## Automated Notification System

A **background notification scheduler** runs alongside the bot, providing proactive deadline management:
- **Implementation**: Asynchronous task created with `asyncio.create_task()`, properly cancelled during shutdown
- **Check Frequency**: Every 30 minutes
- **Notification Types**:
  - **24-hour reminder**: Sent to task assignee 24 hours before deadline
  - **3-hour reminder**: Sent to task assignee 3 hours before deadline  
  - **Overdue alert**: Sent to all admins for tasks past deadline
- **Smart Tracking**: Uses `task_notifications` table to prevent duplicate notifications
- **NULL-safe**: Handles tasks with missing descriptions gracefully
- **Priority-aware**: Includes priority emoji indicators in notifications
- **Quick Actions**: All notifications include "Open Task" button for direct access
- **Logging**: Comprehensive logging with emoji indicators for monitoring

## Logging System

A **centralized logging system** is configured via `app.logging_config`, providing:
- A rotating file handler (`logs/bot.log`) for detailed logs.
- A console handler for real-time output.
- Structured log format including timestamp, module, level, and message.
- Different logging levels for file (DEBUG) and console (INFO).

## Deployment & Management

- **Environment Variables**: Managed via Replit Secrets or a `.env` file for `TELEGRAM_BOT_TOKEN`, `DATABASE_URL`, and `SESSION_SECRET`.
- **`START_BOT.sh`**: An interactive script for starting, stopping, restarting, and checking bot status, with options for systemd service management on Ubuntu servers.

## Polling vs. Webhook

The system uses **Polling** for its simplicity, no HTTPS requirement, and ease of debugging and deployment without needing a public application.

## Design Decisions

- **Python + aiogram**: Chosen for development ease, async capabilities, and community support.
- **Polling**: Selected for simplified setup and development.
- **PostgreSQL**: For reliability, transaction support, and relational features.
- **No AI**: Ensures free operation and predictable behavior.
- **Modular Architecture & Router Pattern**: For improved maintainability, testability, and adherence to best practices.

## UI/UX Decisions

- **Interactive Inline Buttons**: Primary mode of user interaction.
- **Role-Based Access**: Distinguishes admin and employee functionalities.
- **Task Photo Integration**: Enhances task clarity.
- **"Open Task" Button**: Quick navigation from notifications and reminders.
- **Comprehensive Logging**: Uses emoji indicators for clear monitoring.
- **Pagination**: Implemented for task lists (10 tasks per page) with navigation and page counters.
- **Task Search**: Allows searching tasks by title and description, accessible to all users with appropriate rights.
- **Admin Dashboard**: Provides real-time statistics (total, active, completed, overdue tasks, status/priority distribution, top performers) with a refresh option.
- **Excel Reports**: Admins can generate detailed Excel reports with 4 sheets:
  - **Statistics**: Overview with key metrics
  - **Charts**: Visual distribution of status, priority, and performance
  - **Completed Tasks**: Detailed list with timestamps and assignees
  - **Overdue Tasks**: Detailed list with days overdue (7+ days highlighted in red)
- **Automated Reminders**: Proactive 24h/3h deadline notifications and overdue alerts to keep tasks on track.
- **Timezone Support & Time Selection** (NEW):
  - **Configurable Timezone**: Default is Europe/Moscow (UTC+3), easily changed in `app/config.py`
  - **Two-Step Date/Time Selection**: Users first select a date, then choose a specific time
  - **Time Selection Options**: 09:00-23:59 with quick-select buttons (09:00, 12:00, 15:00, 18:00, 21:00, etc.) and manual input
  - **Timezone-Aware Storage**: All timestamps stored as `TIMESTAMP WITH TIME ZONE` in PostgreSQL
  - **Consistent Formatting**: All dates/times displayed as "DD.MM.YYYY HH:MM (МСК)" throughout the interface
  - **Utility Functions**: `get_now()` returns current time in configured timezone, `combine_datetime()` creates timezone-aware datetime from date and time strings

# External Dependencies

## Database & Storage
- **SQLite3**: Файловая база данных (встроена в Python, установка не требуется).

## Telegram Integration
- **aiogram**: Asynchronous framework for Telegram Bot API.
- **aiohttp**: Asynchronous HTTP client for network requests.
- **Telegram Bot API**: Core interaction interface.

## Utilities
- **python-dotenv**: For loading environment variables.
- **typing-extensions**: For extended type hinting support.
- **pytz**: For timezone support and datetime localization (Europe/Moscow UTC+3 by default).
- **openpyxl**: For Excel report generation.
- **matplotlib**: For creating charts in Excel reports.
- **Pillow**: For image processing in reports.