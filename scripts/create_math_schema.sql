CREATE DATABASE IF NOT EXISTS math_brain
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE math_brain;

CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  nickname VARCHAR(64) NULL,
  email VARCHAR(128) NULL,
  role ENUM('student', 'teacher', 'admin') NOT NULL DEFAULT 'student',
  current_stage VARCHAR(16) NOT NULL DEFAULT '大一',
  status TINYINT NOT NULL DEFAULT 1,
  last_login_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_users_username (username),
  UNIQUE KEY uk_users_email (email),
  KEY idx_users_role_status (role, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS teacher_profiles (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  display_name VARCHAR(64) NOT NULL,
  organization VARCHAR(160) NULL,
  verification_status ENUM('verified', 'disabled') NOT NULL DEFAULT 'verified',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_teacher_profiles_user (user_id),
  CONSTRAINT fk_teacher_profiles_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS auth_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  token_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  expires_at DATETIME NOT NULL,
  last_seen_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_auth_sessions_token (token_hash),
  KEY idx_auth_sessions_user_active (user_id, revoked_at, expires_at),
  CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS classes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  teacher_id BIGINT UNSIGNED NOT NULL,
  name VARCHAR(100) NOT NULL,
  stage VARCHAR(16) NOT NULL,
  course VARCHAR(128) NOT NULL,
  invite_code CHAR(8) CHARACTER SET ascii COLLATE ascii_bin NOT NULL,
  status ENUM('active', 'archived') NOT NULL DEFAULT 'active',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_classes_invite_code (invite_code),
  UNIQUE KEY uk_classes_teacher_name (teacher_id, name),
  KEY idx_classes_teacher_status (teacher_id, status),
  CONSTRAINT fk_classes_teacher FOREIGN KEY (teacher_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS class_members (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  class_id BIGINT UNSIGNED NOT NULL,
  student_id BIGINT UNSIGNED NOT NULL,
  status ENUM('active', 'removed') NOT NULL DEFAULT 'active',
  joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  removed_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_class_members_class_student (class_id, student_id),
  KEY idx_class_members_student_status (student_id, status),
  KEY idx_class_members_class_status (class_id, status),
  CONSTRAINT fk_class_members_class FOREIGN KEY (class_id) REFERENCES classes (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_class_members_student FOREIGN KEY (student_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  actor_user_id BIGINT UNSIGNED NOT NULL,
  action VARCHAR(80) NOT NULL,
  entity_type VARCHAR(48) NOT NULL,
  entity_id BIGINT UNSIGNED NULL,
  payload JSON NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_audit_logs_actor_time (actor_user_id, created_at),
  KEY idx_audit_logs_entity (entity_type, entity_id),
  CONSTRAINT fk_audit_logs_actor FOREIGN KEY (actor_user_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  session_id CHAR(36) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  role ENUM('user', 'assistant') NOT NULL,
  content LONGTEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_chat_messages_user_time (user_id, created_at),
  KEY idx_chat_messages_session_time (session_id, created_at),
  CONSTRAINT fk_chat_messages_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS user_goal_settings (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  target_course VARCHAR(128) NOT NULL DEFAULT '高等数学',
  target_stage VARCHAR(16) NOT NULL DEFAULT '大一',
  weekly_hours DECIMAL(4,1) NOT NULL DEFAULT 8.0,
  exam_date DATE NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_user_goal_settings_user (user_id),
  CONSTRAINT fk_user_goal_settings_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS source_attributions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_name VARCHAR(160) NOT NULL,
  source_url VARCHAR(512) NOT NULL,
  license_name VARCHAR(160) NOT NULL,
  license_url VARCHAR(512) NOT NULL,
  usage_note TEXT NULL,
  downloaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_source_attributions_name (source_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS math_stages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  stage_name VARCHAR(16) NOT NULL,
  stage_order TINYINT UNSIGNED NOT NULL,
  title VARCHAR(128) NOT NULL,
  goal_text TEXT NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_math_stages_name (stage_name),
  UNIQUE KEY uk_math_stages_order (stage_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS math_courses (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  stage_id BIGINT UNSIGNED NOT NULL,
  course_name VARCHAR(128) NOT NULL,
  course_group VARCHAR(64) NOT NULL,
  course_order SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  description TEXT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_math_courses_stage_course (stage_id, course_name),
  KEY idx_math_courses_group (course_group),
  CONSTRAINT fk_math_courses_stage
    FOREIGN KEY (stage_id) REFERENCES math_stages (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS knowledge_nodes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  node_code VARCHAR(120) NOT NULL,
  parent_id BIGINT UNSIGNED NULL,
  stage_name VARCHAR(16) NOT NULL,
  course_name VARCHAR(128) NOT NULL,
  name VARCHAR(160) NOT NULL,
  level TINYINT UNSIGNED NOT NULL,
  sort_order INT UNSIGNED NOT NULL DEFAULT 0,
  description TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_knowledge_nodes_code (node_code),
  KEY idx_knowledge_nodes_parent (parent_id),
  KEY idx_knowledge_nodes_stage_course (stage_name, course_name),
  KEY idx_knowledge_nodes_name (name),
  CONSTRAINT fk_knowledge_nodes_parent
    FOREIGN KEY (parent_id) REFERENCES knowledge_nodes (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS mistake_tags (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tag_name VARCHAR(80) NOT NULL,
  description TEXT NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_mistake_tags_name (tag_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS questions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  source_id BIGINT UNSIGNED NOT NULL,
  source_question_no VARCHAR(128) NOT NULL,
  source_path VARCHAR(768) NOT NULL,
  question_type ENUM('choice','blank','calculation','proof','comprehensive') NOT NULL,
  stage VARCHAR(16) NOT NULL,
  course VARCHAR(128) NOT NULL,
  knowledge_node_id BIGINT UNSIGNED NULL,
  knowledge_tag VARCHAR(160) NOT NULL,
  fine_tag VARCHAR(160) NOT NULL,
  difficulty TINYINT UNSIGNED NOT NULL DEFAULT 3,
  question_text LONGTEXT NOT NULL,
  option_a TEXT NULL,
  option_b TEXT NULL,
  option_c TEXT NULL,
  option_d TEXT NULL,
  correct_answer VARCHAR(16) NULL,
  standard_answer LONGTEXT NOT NULL,
  analysis_text LONGTEXT NOT NULL,
  key_steps JSON NOT NULL,
  common_errors JSON NOT NULL,
  mistake_tags JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_questions_source_no (source_id, source_question_no),
  KEY idx_questions_stage_course (stage, course),
  KEY idx_questions_type (question_type),
  KEY idx_questions_knowledge (knowledge_tag, fine_tag),
  KEY idx_questions_difficulty (difficulty),
  KEY idx_questions_knowledge_node (knowledge_node_id),
  CONSTRAINT fk_questions_source
    FOREIGN KEY (source_id) REFERENCES source_attributions (id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT fk_questions_knowledge_node
    FOREIGN KEY (knowledge_node_id) REFERENCES knowledge_nodes (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE,
  CONSTRAINT chk_questions_difficulty
    CHECK (difficulty BETWEEN 1 AND 5)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS practice_records (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(64) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  question_id BIGINT UNSIGNED NOT NULL,
  selected_answer VARCHAR(16) NULL,
  answer_text LONGTEXT NULL,
  is_correct TINYINT(1) NULL,
  score DECIMAL(5,2) NULL,
  mistake_tags JSON NULL,
  time_spent_seconds INT UNSIGNED NOT NULL DEFAULT 0,
  practice_mode ENUM('daily','chapter','mock','wrong_book','custom','assessment') NOT NULL DEFAULT 'custom',
  review_status ENUM('auto_graded','pending','graded') NOT NULL DEFAULT 'auto_graded',
  teacher_score DECIMAL(5,2) NULL,
  teacher_feedback TEXT NULL,
  answered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_practice_records_task (task_id),
  KEY idx_practice_records_user_time (user_id, answered_at),
  KEY idx_practice_records_question (question_id),
  KEY idx_practice_records_review (review_status, answered_at),
  CONSTRAINT fk_practice_records_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_practice_records_question
    FOREIGN KEY (question_id) REFERENCES questions (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS uploaded_files (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  storage_key VARCHAR(768) NOT NULL,
  mime_type VARCHAR(64) NOT NULL,
  size_bytes INT UNSIGNED NOT NULL,
  sha256 CHAR(64) NOT NULL,
  width INT UNSIGNED NOT NULL,
  height INT UNSIGNED NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_uploaded_files_storage (storage_key),
  KEY idx_uploaded_files_user_time (user_id, created_at),
  CONSTRAINT fk_uploaded_files_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS answer_attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  practice_record_id BIGINT UNSIGNED NOT NULL,
  uploaded_file_id BIGINT UNSIGNED NOT NULL,
  sort_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_answer_attachments_file (uploaded_file_id),
  KEY idx_answer_attachments_record (practice_record_id, sort_order),
  CONSTRAINT fk_answer_attachments_record FOREIGN KEY (practice_record_id) REFERENCES practice_records (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_answer_attachments_file FOREIGN KEY (uploaded_file_id) REFERENCES uploaded_files (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS assessment_sessions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id CHAR(36) NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  stage VARCHAR(16) NOT NULL,
  status ENUM('in_progress','completed','abandoned') NOT NULL DEFAULT 'in_progress',
  question_count SMALLINT UNSIGNED NOT NULL,
  summary_json JSON NULL,
  plan_json JSON NULL,
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assessment_sessions_task (task_id),
  KEY idx_assessment_sessions_user_status (user_id, status, started_at),
  CONSTRAINT fk_assessment_sessions_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS assessment_session_questions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  assessment_id BIGINT UNSIGNED NOT NULL,
  question_id BIGINT UNSIGNED NOT NULL,
  sort_order SMALLINT UNSIGNED NOT NULL,
  practice_record_id BIGINT UNSIGNED NULL,
  answered_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assessment_question (assessment_id, question_id),
  UNIQUE KEY uk_assessment_order (assessment_id, sort_order),
  KEY idx_assessment_question_record (practice_record_id),
  CONSTRAINT fk_assessment_question_session FOREIGN KEY (assessment_id) REFERENCES assessment_sessions (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assessment_question_question FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_assessment_question_record FOREIGN KEY (practice_record_id) REFERENCES practice_records (id) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS learning_plans (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NULL,
  stage VARCHAR(16) NOT NULL,
  course VARCHAR(128) NOT NULL,
  plan_name VARCHAR(160) NOT NULL,
  plan_json JSON NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_learning_plans_user (user_id),
  KEY idx_learning_plans_stage_course (stage, course),
  CONSTRAINT fk_learning_plans_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
