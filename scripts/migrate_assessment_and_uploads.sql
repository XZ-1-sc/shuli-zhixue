USE math_brain;

ALTER TABLE practice_records
  MODIFY COLUMN practice_mode ENUM('daily','chapter','mock','wrong_book','custom','assessment')
    NOT NULL DEFAULT 'custom',
  ADD COLUMN review_status ENUM('auto_graded','pending','graded')
    NOT NULL DEFAULT 'auto_graded' AFTER practice_mode,
  ADD COLUMN teacher_score DECIMAL(5,2) NULL AFTER review_status,
  ADD COLUMN teacher_feedback TEXT NULL AFTER teacher_score,
  ADD KEY idx_practice_records_review (review_status, answered_at);

CREATE TABLE uploaded_files (
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
  CONSTRAINT fk_uploaded_files_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE answer_attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  practice_record_id BIGINT UNSIGNED NOT NULL,
  uploaded_file_id BIGINT UNSIGNED NOT NULL,
  sort_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_answer_attachments_file (uploaded_file_id),
  KEY idx_answer_attachments_record (practice_record_id, sort_order),
  CONSTRAINT fk_answer_attachments_record
    FOREIGN KEY (practice_record_id) REFERENCES practice_records (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_answer_attachments_file
    FOREIGN KEY (uploaded_file_id) REFERENCES uploaded_files (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assessment_sessions (
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
  CONSTRAINT fk_assessment_sessions_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assessment_session_questions (
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
  CONSTRAINT fk_assessment_question_session
    FOREIGN KEY (assessment_id) REFERENCES assessment_sessions (id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,
  CONSTRAINT fk_assessment_question_question
    FOREIGN KEY (question_id) REFERENCES questions (id)
    ON DELETE RESTRICT
    ON UPDATE CASCADE,
  CONSTRAINT fk_assessment_question_record
    FOREIGN KEY (practice_record_id) REFERENCES practice_records (id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
