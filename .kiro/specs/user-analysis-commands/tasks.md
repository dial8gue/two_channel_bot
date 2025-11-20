# Implementation Plan

- [x] 1. Add configuration support for user analysis periods





  - Add `anal_period_hours` and `deep_anal_period_hours` fields to Config dataclass
  - Add environment variable loading with defaults (6 and 12 hours)
  - Add validation for positive integer values
  - Update .env.example with documentation for new variables
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
-

- [x] 2. Implement wait time formatting utility



  - [x] 2.1 Add `format_debounce_wait_time` method to MessageFormatter


    - Convert seconds to hours, minutes, seconds components
    - Format string with Russian abbreviations (ч, мин, сек)
    - Omit zero components (hours if < 1 hour, minutes if < 1 minute)
    - Handle edge cases (0 seconds, very large values)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_





- [x] 3. Enhance debounce manager with remaining time support



  - [x] 3.1 Update `can_execute` method to return tuple (bool, float)


    - Return both execution permission and remaining seconds
    - Maintain backward compatibility with existing callers
    - Calculate remaining time from last execution timestamp
    - _Requirements: 4.1, 7.4_
  
  - [x] 3.2 Add `get_remaining_time` method

    - Query last execution time for operation
    - Calculate remaining seconds in debounce period
    - Return 0 if not debounced
    - _Requirements: 4.1_

- [x] 4. Update analysis service for chat-level debounce






  - [x] 4.1 Add `analyze_messages_with_debounce` method

    - Accept chat_id, user_id, operation_type, and bypass_debounce parameters
    - Format operation key as "{operation_type}:{chat_id}"
    - Check debounce using formatted operation key (skip if bypass_debounce=True)
    - Call existing `analyze_messages` method for actual analysis
    - Raise ValueError with remaining seconds if debounced
    - _Requirements: 1.1, 1.5, 2.1, 2.5, 5.1, 5.2, 5.3, 7.1, 7.2, 7.3, 7.4_
  
  - [x] 4.2 Update debounce check to use chat-level operation key


    - Modify operation key format to include chat_id
    - Ensure different chats have independent debounce tracking
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 5. Create user router with analysis commands




  - [x] 5.1 Create `bot/routers/user_router.py` file

    - Import required dependencies (Router, Message, Command, ChatType, etc.)
    - Create router instance with name "user_router"
    - _Requirements: 1.1, 2.1, 6.1, 6.2, 6.3_
  
  - [x] 5.2 Implement `/anal` command handler

    - Filter for group and supergroup chat types only
    - Check if user is admin (compare user_id with config.admin_id)
    - Call `analyze_messages_with_debounce` with anal_period_hours
    - Pass bypass_debounce=True for admin users
    - Handle ValueError for debounce rejection
    - Format debounce error message with wait time
    - Send analysis result to the group chat
    - Log command execution with user_id and chat_id
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4_
  

  - [x] 5.3 Implement `/deep_anal` command handler
    - Filter for group and supergroup chat types only
    - Check if user is admin (compare user_id with config.admin_id)
    - Call `analyze_messages_with_debounce` with deep_anal_period_hours
    - Pass bypass_debounce=True for admin users
    - Handle ValueError for debounce rejection
    - Format debounce error message with wait time
    - Send analysis result to the group chat
    - Log command execution with user_id and chat_id
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4_
  

  - [x] 5.4 Implement `create_user_router` factory function

    - Accept config parameter
    - Return configured router instance
    - _Requirements: 1.1, 2.1_

- [x] 6. Register user router in bot main





  - Import user_router module in `bot/main.py`
  - Create user router instance using `create_user_router(config)`
  - Register router with dispatcher using `dp.include_router(user_router)`
  - Ensure router is registered before starting bot
  - _Requirements: 1.1, 2.1_


- [x] 7. Update environment configuration documentation




  - Add ANAL_PERIOD_HOURS to .env.example with description
  - Add DEEP_ANAL_PERIOD_HOURS to .env.example with description
  - Document default values (6 and 12 hours)
  - Add comment explaining debounce applies to user commands
  - _Requirements: 3.1, 3.2, 3.3, 3.4_
