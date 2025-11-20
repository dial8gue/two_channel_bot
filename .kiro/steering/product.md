# Product Overview

Telegram Analytics Bot - A Telegram bot that analyzes group chat messages using OpenAI's LLM API.

## Core Functionality

- Collects messages from Telegram group chats automatically
- Analyzes message history using OpenAI API to generate summaries
- Provides insights on: who discussed what, most discussed posts, users with most reactions
- Stores messages in SQLite database with configurable retention period
- Implements caching to reduce API costs and debouncing to prevent spam

## Key Features

- Admin-only commands for analysis and configuration
- Debug mode for testing (sends results to admin only)
- Automatic cleanup of old messages based on retention policy
- Three-tier message formatting fallback (Markdown → HTML → Plain text)
- Reaction tracking and analysis

## User Roles

- Admin: Single user (configured via ADMIN_ID) with full access to all commands
- Group members: Messages are collected passively, no direct interaction

## Language

Primary language is Russian (commands, responses, documentation in README)
