# Overview

This project is a full-featured asynchronous Telegram bot for task management, built with Python and `aiogram`. It operates via polling, offering a cost-effective and robust solution for team task coordination. Key features include a modular architecture, role-based access (admin/employee), SQLite for local data storage, interactive inline buttons, a whitelist authorization system, FSM for task and user management, comprehensive error handling, task photo support, automated multi-tier deadline notifications (8h/4h/final hour continuous reminders, overdue alerts), advanced statistics with Excel export, pagination, search, full timezone support with precise time selection, **change assignee functionality with notifications**, and **task return with required admin comments**. The bot consistently displays user real names in "First Last (@username)" format across the interface, aiming to provide efficient and proactive task management.

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

The application uses **Python 3.11 and aiogram 3.22**, leveraging `asyncio` for asynchronous processing in polling mode. It employs `MemoryStorage` for the FSM and `pytz` for comprehensive timezone support, ensuring all timestamps are correctly handled in the Kaliningrad timezone (Europe/Kaliningrad UTC+2). The architecture is modular and router-based.

## Modular Structure

The codebase is organized into `app/main.py` (bot initialization, router registration), `app/config.py` (centralized constants), `app/logging_config.py`, `app/database.py` (SQLite connection), `app/states.py` (FSM definitions), `app/keyboards/`, `app/services/` (business logic), and `app/handlers/`.

## Database Layer

**SQLite3** is used for data management, featuring a schema with `users`, `tasks`, `allowed_users`, and `task_notifications` tables. It includes enum types for roles, priorities, and statuses, and foreign key relationships. Key entities include user profiles (Telegram ID, name, role), tasks (title, description, priority, status, due date, assignment, photo), allowed users for whitelist authorization, and task notification tracking.

## Bot Architecture

The bot utilizes the **Aiogram 3 Router Pattern** with `core_router`, `statuses_router`, and `photos_router`. Asynchronous handlers validate access rights via the service layer, manage database operations, and send Telegram API responses.

## Automated Notification System

A **background notification scheduler** runs every 5 minutes, providing proactive deadline management. It sends 8-hour and 4-hour reminders once, and **continuous "final hour" alerts every 5 minutes** during the last hour before a deadline. Overdue alerts are sent to both the executor and all admins. The system uses the `task_notifications` table to prevent duplicate one-time reminders, includes priority indicators, and offers "Open Task" buttons for quick access.

## Logging System

A **centralized logging system** (configured via `app.logging_config`) provides rotating file logs (`logs/bot.log`) and console output. It uses a structured format with different logging levels and emoji indicators for clarity.

## UI/UX Decisions

The bot prioritizes **interactive inline buttons** for user interaction. It features **role-based access**, **task photo integration**, and quick navigation via "Open Task" buttons. Task lists support **pagination** and **search**. An **admin dashboard** provides real-time statistics with Excel export capabilities (including charts, completed, and overdue tasks). **Real names from Telegram profiles** ("First Last (@username)") are consistently displayed for user identification. The system includes **auto-assignment** for unassigned tasks and comprehensive **timezone support** with two-step date/time selection (date then specific time from 09:00-23:59 with quick-select options), storing timestamps as `TIMESTAMP WITH TIME ZONE`.

# External Dependencies

-   **SQLite3**: Embedded database.
-   **aiogram**: Telegram Bot API framework.
-   **aiohttp**: Asynchronous HTTP client.
-   **python-dotenv**: For environment variable management.
-   **pytz**: For timezone handling and localization.
-   **openpyxl**: For Excel report generation.
-   **matplotlib**: For creating charts in Excel reports.
-   **Pillow**: For image processing in reports.