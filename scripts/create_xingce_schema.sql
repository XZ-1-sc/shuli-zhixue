CREATE DATABASE IF NOT EXISTS xingce
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE xingce;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户ID',
  username VARCHAR(64) NOT NULL COMMENT '登录用户名',
  password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
  nickname VARCHAR(64) NULL COMMENT '用户昵称',
  email VARCHAR(128) NULL COMMENT '邮箱',
  phone VARCHAR(32) NULL COMMENT '手机号',
  target_exam VARCHAR(128) NULL COMMENT '目标考试',
  current_level ENUM('beginner', 'intermediate', 'advanced') NOT NULL DEFAULT 'beginner' COMMENT '当前水平',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '状态：1启用，0停用',
  last_login_at DATETIME NULL COMMENT '最后登录时间',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_email (email),
  UNIQUE KEY uk_users_phone (phone),
  KEY idx_users_status (status),
  KEY idx_users_target_exam (target_exam)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户表';

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '知识节点ID',
  node_code VARCHAR(100) NOT NULL COMMENT '节点编码',
  parent_id BIGINT UNSIGNED NULL COMMENT '父节点ID',
  module VARCHAR(50) NOT NULL COMMENT '所属模块',
  name VARCHAR(100) NOT NULL COMMENT '节点名称',
  level TINYINT UNSIGNED NOT NULL COMMENT '节点层级：1模块，2知识点，3细颗粒度',
  sort_order INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '排序号',
  description TEXT NULL COMMENT '节点说明',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_knowledge_nodes_code (node_code),
  KEY idx_knowledge_nodes_parent (parent_id),
  KEY idx_knowledge_nodes_module_level (module, level),
  CONSTRAINT fk_knowledge_nodes_parent
    FOREIGN KEY (parent_id) REFERENCES knowledge_nodes (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='知识节点表';

CREATE TABLE IF NOT EXISTS questions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '题目ID',
  question_text TEXT NOT NULL COMMENT '题干',
  option_a TEXT NOT NULL COMMENT '选项A',
  option_b TEXT NOT NULL COMMENT '选项B',
  option_c TEXT NOT NULL COMMENT '选项C',
  option_d TEXT NOT NULL COMMENT '选项D',
  correct_answer ENUM('A', 'B', 'C', 'D') NOT NULL COMMENT '正确答案',
  module VARCHAR(50) NOT NULL COMMENT '所属模块',
  knowledge_node_id BIGINT UNSIGNED NULL COMMENT '知识节点ID',
  knowledge_tag VARCHAR(100) NULL COMMENT '知识点标签',
  difficulty TINYINT UNSIGNED NOT NULL DEFAULT 3 COMMENT '难度：1-5',
  source_name VARCHAR(128) NULL COMMENT '题目来源',
  source_question_no VARCHAR(32) NULL COMMENT '来源题号',
  source_url VARCHAR(512) NULL COMMENT '来源链接',
  analysis_text TEXT NULL COMMENT '解析',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_questions_module_tag (module, knowledge_tag),
  KEY idx_questions_knowledge_node (knowledge_node_id),
  KEY idx_questions_answer (correct_answer),
  KEY idx_questions_difficulty (difficulty),
  UNIQUE KEY uk_questions_source_no (source_name, source_question_no),
  CONSTRAINT fk_questions_knowledge_node
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT chk_questions_difficulty
    CHECK (difficulty BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='题目表';

CREATE TABLE IF NOT EXISTS practice_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '做题记录ID',
  task_id VARCHAR(64) NOT NULL COMMENT '练习任务ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  question_id BIGINT UNSIGNED NOT NULL COMMENT '题目ID',
  selected_answer ENUM('A', 'B', 'C', 'D') NOT NULL COMMENT '用户选择',
  is_correct TINYINT(1) NOT NULL COMMENT '是否正确',
  time_spent_seconds INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '作答耗时（秒）',
  attempt_no INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '第几次作答',
  practice_mode ENUM('daily', 'chapter', 'mock', 'wrong_book', 'custom') NOT NULL DEFAULT 'custom' COMMENT '练习模式',
  answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作答时间',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_practice_records_task (task_id),
  KEY idx_practice_records_user_time (user_id, answered_at),
  KEY idx_practice_records_user_task (user_id, task_id),
  KEY idx_practice_records_question (question_id),
  KEY idx_practice_records_user_question (user_id, question_id),
  KEY idx_practice_records_correct (is_correct),
  CONSTRAINT fk_practice_records_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_practice_records_question
    FOREIGN KEY (question_id) REFERENCES questions (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='做题记录表';

CREATE TABLE IF NOT EXISTS negotiation_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '协商日志ID',
  conversation_id CHAR(36) NOT NULL COMMENT '一次调度流程的会话ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  round_no TINYINT UNSIGNED NOT NULL COMMENT '协商轮次',
  speaker ENUM('diagnostician', 'strategist', 'orchestrator') NOT NULL COMMENT '发言角色',
  message_type VARCHAR(64) NOT NULL COMMENT '消息类型',
  content LONGTEXT NOT NULL COMMENT '对话内容',
  needs_rediagnosis TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否要求重新诊断',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_negotiation_log_conversation (conversation_id, round_no),
  KEY idx_negotiation_log_user_time (user_id, created_at),
  KEY idx_negotiation_log_speaker_type (speaker, message_type),
  CONSTRAINT fk_negotiation_log_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='自然语言协商日志表';

CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '聊天消息ID',
  session_id CHAR(36) NOT NULL COMMENT '前端会话ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  role ENUM('user', 'assistant') NOT NULL COMMENT '消息角色',
  content LONGTEXT NOT NULL COMMENT '消息内容',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_chat_messages_user_time (user_id, created_at),
  KEY idx_chat_messages_session_time (session_id, created_at),
  KEY idx_chat_messages_role (role),
  CONSTRAINT fk_chat_messages_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='小逻对话历史表';

CREATE TABLE IF NOT EXISTS user_study_plans (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '备考方案ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  exam_type VARCHAR(64) NOT NULL COMMENT '考试类型',
  job_category VARCHAR(128) NOT NULL COMMENT '岗位类别',
  plan_name VARCHAR(128) NOT NULL COMMENT '方案名称',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_study_plans_user (user_id),
  KEY idx_user_study_plans_exam (exam_type, job_category),
  CONSTRAINT fk_user_study_plans_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户备考方案表';

CREATE TABLE IF NOT EXISTS user_goal_settings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '目标设置ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  target_score DECIMAL(5,1) NOT NULL DEFAULT 78.0 COMMENT '目标分数',
  exam_date DATE NOT NULL COMMENT '目标考试日期',
  target_exam VARCHAR(128) NOT NULL DEFAULT '国考' COMMENT '目标考试',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_goal_settings_user (user_id),
  CONSTRAINT fk_user_goal_settings_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='用户目标设置表';

CREATE TABLE IF NOT EXISTS subjective_practice_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主观题记录ID',
  task_id VARCHAR(64) NOT NULL COMMENT '练习任务ID',
  user_id BIGINT UNSIGNED NOT NULL COMMENT '用户ID',
  question_id BIGINT UNSIGNED NOT NULL COMMENT '主观题ID',
  question_type VARCHAR(32) NOT NULL COMMENT '题型',
  module VARCHAR(50) NOT NULL COMMENT '所属模块',
  knowledge_tag VARCHAR(100) NOT NULL COMMENT '知识点标签',
  answer_text LONGTEXT NOT NULL COMMENT '用户答案',
  reference_answer LONGTEXT NOT NULL COMMENT '参考答案',
  score TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '关键词评分',
  time_spent_seconds INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '作答耗时（秒）',
  practice_mode ENUM('daily','chapter','mock','wrong_book','custom') NOT NULL DEFAULT 'custom' COMMENT '练习模式',
  answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '作答时间',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  KEY idx_subjective_user_time (user_id, answered_at),
  KEY idx_subjective_task (task_id),
  KEY idx_subjective_module_tag (module, knowledge_tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='主观题做题记录表';
