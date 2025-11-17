# Overview

This is a Mastra-based AI automation platform built for Replit that enables task management via Telegram webhooks. The system uses Mastra's agent framework to process natural language messages, create and manage tasks, and interact with users through a Telegram bot interface.

The application demonstrates a production-ready implementation of:
- Command-based bot without AI (fully free)
- Webhook-triggered workflows for real-time interaction
- Database-backed task management system with role-based access (admin/employee)
- Durable execution with Inngest integration
- Telegram slash commands in Russian

## Current Status (November 17, 2025)

✅ **Production-ready and validated (Command-Based, No AI)**

All core components have been reimplemented without AI and passed architect review:
- Database schema with users and tasks tables
- Command handler for Telegram commands (no AI/LLM)
- Two-step workflow (parse command + send response)
- Telegram webhook trigger
- **Validated error handling:**
  - Task assignment with Telegram ID lookup
  - Numeric ID validation (только цифры)
  - Clear error messages for missing users
  - Production logging for debugging
- **Fully free** - no AI API costs

**Recent Critical Fixes (Nov 17, 2025):**
- ✅ Fixed task assignment: now correctly resolves Telegram IDs to internal user IDs
- ✅ Added validation: rejects non-numeric Telegram IDs with clear error messages
- ✅ Added production logging: console.log statements for assignment flow debugging
- ✅ Improved user feedback: shows assigned user info in success responses

**Changes from previous version:**
- ❌ Removed AI agent (GPT-5) and natural language understanding
- ✅ Added command parser for explicit commands (/start, /create_task, etc.)
- ✅ Completely free operation (no LLM API calls)
- ✅ Faster response times
- ✅ Predictable behavior

**Next step**: Publish the application and register the Telegram webhook using the guide in `TELEGRAM_BOT_GUIDE.md`

# User Preferences

Preferred communication style: Simple, everyday language (Russian).

# System Architecture

## Core Framework

**Mastra v0.20.0** serves as the foundation, providing:
- Agent orchestration with LLM reasoning
- Workflow execution with step-based composition
- Memory management for conversation persistence
- Tool integration for external functionality

## Database Layer

**PostgreSQL with Drizzle ORM** handles all persistent data:
- **Schema Design**: Three main tables (users, tasks) with enum types for roles, priorities, and task statuses
- **Relations**: Foreign key relationships between users and tasks (assignedTo, createdBy)
- **Connection**: Uses `postgres-js` driver with connection string from `DATABASE_URL` environment variable
- **Migration Strategy**: Drizzle Kit manages schema migrations with output to `./drizzle` directory

**Key Entities**:
- Users: Telegram ID (unique), username, role (admin/employee), timestamps
- Tasks: Title, description, priority (low/medium/high/urgent), status (pending/in_progress/completed/rejected), due date, assignment tracking

## Command Handler Architecture

**Command Parser** (src/handlers/telegramCommandHandler.ts) processes Telegram commands:
- Explicit command parsing (/ start, /create_task, /my_tasks, etc.)
- Direct database operations without LLM
- Role-based access control
- Parameter parsing for task creation
- No AI dependencies - fully deterministic

**Handler Pattern**: Single command handler processes all Telegram commands and returns structured responses.

## Workflow Orchestration

**Inngest Integration** provides durable execution:
- Workflows defined as composable steps
- Automatic retry handling for transient failures
- Suspend/resume capability for human-in-the-loop scenarios
- Real-time monitoring via Inngest middleware

**Workflow Pattern**: Event-driven execution triggered by Telegram webhooks, with steps that can call agents, tools, or external APIs.

## Webhook Integration

**Telegram Bot API** serves as the primary user interface:
- POST endpoint at `/webhooks/telegram/action` receives messages
- Webhook registration script for Replit deployment
- Message payload processing with telegramId extraction
- Bot token authentication via environment variable

**Trigger System**: Modular trigger registration pattern allows adding new connectors (Slack, Linear, etc.) by following the template in `src/triggers/`.

## Logging & Observability

**Production Pino Logger** (custom implementation):
- JSON-formatted structured logging
- Configurable log levels (DEBUG, INFO, WARN, ERROR)
- ISO timestamp formatting
- Request/response tracking through Mastra integration

## Development Tools

**TypeScript Configuration**:
- ES2022 target with ES module system
- Bundler module resolution for modern tooling
- Strict type checking enabled
- No emit mode for type checking only

**Mastra CLI**:
- `mastra dev` for local development with hot reload
- `mastra build` for production builds
- Integrated playground UI for testing workflows/agents

## Design Decisions

**Why PostgreSQL over LibSQL**: Production deployments benefit from PostgreSQL's proven reliability, pgvector extension for semantic search, and widespread hosting support. LibSQL shown in examples but Postgres recommended for production.

**Why Inngest**: Provides durable execution out-of-the-box without managing infrastructure. Critical for production reliability when workflows need to survive server restarts or handle long-running operations.

**Why Single Agent**: Task domain is well-defined enough that a single specialized agent handles all operations effectively. Agent networks would add complexity without clear benefit for this use case.

**Why Telegram**: Provides instant messaging interface familiar to users, webhook-based integration, and no need for separate frontend development. Easy to extend to other messaging platforms using same trigger pattern.

# External Dependencies

## AI/LLM Services
- **None**: This version uses command-based approach without any AI/LLM
- **Previous version used**: OpenAI GPT-5 via Replit AI Integrations (removed)

## Database & Storage
- **PostgreSQL**: Primary database (connection via `DATABASE_URL`)
- **Drizzle ORM**: Type-safe database toolkit (v0.44.7)
- **postgres-js**: PostgreSQL client driver (v3.4.7)

## Messaging Platform
- **Telegram Bot API**: Webhook integration (requires `TELEGRAM_BOT_TOKEN`)
- **@slack/web-api**: Slack integration capability (v7.9.3)

## Workflow Orchestration
- **Inngest**: Durable execution platform (v3.40.2)
- **@inngest/realtime**: Real-time workflow monitoring

## Mastra Ecosystem
- **@mastra/core**: Framework foundation (v0.20.0)
- **@mastra/pg**: PostgreSQL adapter (v0.17.1)
- **@mastra/memory**: Conversation persistence (v0.15.5)
- **@mastra/inngest**: Inngest integration (v0.16.0)
- **@mastra/loggers**: Logging abstractions (v0.10.15)
- **@mastra/mcp**: MCP protocol support (v0.13.3)

## Utilities
- **Zod**: Schema validation (v3.25.76)
- **dotenv**: Environment variable management
- **pino**: Structured logging (v9.9.4)
- **tsx**: TypeScript execution (v4.20.3)

## Development
- **TypeScript**: v5.9.3
- **Prettier**: Code formatting (v3.6.2)
- **Node.js**: Requires >=20.9.0