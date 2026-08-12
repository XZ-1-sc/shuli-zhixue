USE math_brain;

INSERT INTO source_attributions (
  source_name, source_url, license_name, license_url, usage_note
)
SELECT
  '教师自建题库', 'local://teacher-authored', '教师原创/内部教学使用',
  'local://teacher-authored', '教师端创建、维护并发布的校内教学题目。'
WHERE NOT EXISTS (
  SELECT 1 FROM source_attributions WHERE source_name = '教师自建题库'
);

ALTER TABLE questions
  ADD COLUMN created_by BIGINT UNSIGNED NULL AFTER source_id,
  ADD COLUMN visibility ENUM('public','class') NOT NULL DEFAULT 'public' AFTER created_by,
  ADD COLUMN publish_status ENUM('draft','published','archived') NOT NULL DEFAULT 'published' AFTER visibility,
  ADD COLUMN version INT UNSIGNED NOT NULL DEFAULT 1 AFTER publish_status,
  ADD COLUMN published_at DATETIME NULL AFTER version,
  ADD COLUMN deleted_at DATETIME NULL AFTER published_at,
  ADD KEY idx_questions_creator_status (created_by, publish_status, deleted_at),
  ADD CONSTRAINT fk_questions_creator
    FOREIGN KEY (created_by) REFERENCES users (id)
    ON DELETE SET NULL ON UPDATE CASCADE;

UPDATE questions
SET published_at = COALESCE(published_at, created_at)
WHERE publish_status = 'published';

CREATE TABLE question_attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  question_id BIGINT UNSIGNED NOT NULL,
  uploaded_file_id BIGINT UNSIGNED NOT NULL,
  attachment_type ENUM('question','analysis') NOT NULL DEFAULT 'question',
  sort_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_question_attachments_file (uploaded_file_id),
  KEY idx_question_attachments_question (question_id, attachment_type, sort_order),
  CONSTRAINT fk_question_attachments_question
    FOREIGN KEY (question_id) REFERENCES questions (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_question_attachments_file
    FOREIGN KEY (uploaded_file_id) REFERENCES uploaded_files (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assignments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  teacher_id BIGINT UNSIGNED NOT NULL,
  class_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(160) NOT NULL,
  description TEXT NULL,
  status ENUM('draft','published','closed','archived') NOT NULL DEFAULT 'draft',
  starts_at DATETIME NULL,
  due_at DATETIME NULL,
  time_limit_minutes SMALLINT UNSIGNED NULL,
  max_attempts TINYINT UNSIGNED NOT NULL DEFAULT 1,
  show_analysis_after_submit TINYINT(1) NOT NULL DEFAULT 1,
  total_score DECIMAL(7,2) NOT NULL DEFAULT 0,
  published_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_assignments_teacher_status (teacher_id, status, created_at),
  KEY idx_assignments_class_status_due (class_id, status, due_at),
  CONSTRAINT fk_assignments_teacher
    FOREIGN KEY (teacher_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assignments_class
    FOREIGN KEY (class_id) REFERENCES classes (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assignment_questions (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  assignment_id BIGINT UNSIGNED NOT NULL,
  question_id BIGINT UNSIGNED NOT NULL,
  sort_order SMALLINT UNSIGNED NOT NULL,
  points DECIMAL(6,2) NOT NULL DEFAULT 10,
  required TINYINT(1) NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assignment_question (assignment_id, question_id),
  UNIQUE KEY uk_assignment_question_order (assignment_id, sort_order),
  KEY idx_assignment_questions_question (question_id),
  CONSTRAINT fk_assignment_questions_assignment
    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assignment_questions_question
    FOREIGN KEY (question_id) REFERENCES questions (id)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assignment_attempts (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  assignment_id BIGINT UNSIGNED NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  attempt_no TINYINT UNSIGNED NOT NULL DEFAULT 1,
  status ENUM('in_progress','submitted','grading','graded','returned') NOT NULL DEFAULT 'in_progress',
  started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  submitted_at DATETIME NULL,
  graded_at DATETIME NULL,
  total_score DECIMAL(7,2) NULL,
  max_score DECIMAL(7,2) NOT NULL DEFAULT 0,
  teacher_feedback TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assignment_attempt (assignment_id, user_id, attempt_no),
  KEY idx_assignment_attempts_student_status (user_id, status, updated_at),
  KEY idx_assignment_attempts_assignment_status (assignment_id, status, submitted_at),
  CONSTRAINT fk_assignment_attempts_assignment
    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assignment_attempts_user
    FOREIGN KEY (user_id) REFERENCES users (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE assignment_answers (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  attempt_id BIGINT UNSIGNED NOT NULL,
  assignment_question_id BIGINT UNSIGNED NOT NULL,
  practice_record_id BIGINT UNSIGNED NULL,
  selected_answer VARCHAR(16) NULL,
  answer_text LONGTEXT NULL,
  attachment_ids JSON NULL,
  time_spent_seconds INT UNSIGNED NOT NULL DEFAULT 0,
  is_correct TINYINT(1) NULL,
  score DECIMAL(6,2) NULL,
  review_status ENUM('saved','auto_graded','pending','graded','returned') NOT NULL DEFAULT 'saved',
  teacher_feedback TEXT NULL,
  answered_at DATETIME NULL,
  reviewed_at DATETIME NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_assignment_answer_question (attempt_id, assignment_question_id),
  UNIQUE KEY uk_assignment_answer_record (practice_record_id),
  KEY idx_assignment_answers_review (review_status, answered_at),
  CONSTRAINT fk_assignment_answers_attempt
    FOREIGN KEY (attempt_id) REFERENCES assignment_attempts (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assignment_answers_question
    FOREIGN KEY (assignment_question_id) REFERENCES assignment_questions (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_assignment_answers_record
    FOREIGN KEY (practice_record_id) REFERENCES practice_records (id)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

ALTER TABLE practice_records
  MODIFY COLUMN practice_mode ENUM('daily','chapter','mock','wrong_book','custom','assessment','assignment')
    NOT NULL DEFAULT 'custom',
  ADD COLUMN assignment_id BIGINT UNSIGNED NULL AFTER practice_mode,
  ADD COLUMN assignment_attempt_id BIGINT UNSIGNED NULL AFTER assignment_id,
  ADD COLUMN reviewer_id BIGINT UNSIGNED NULL AFTER teacher_feedback,
  ADD COLUMN reviewed_at DATETIME NULL AFTER reviewer_id,
  ADD COLUMN correction_required TINYINT(1) NOT NULL DEFAULT 0 AFTER reviewed_at,
  ADD KEY idx_practice_records_assignment (assignment_id, assignment_attempt_id),
  ADD KEY idx_practice_records_reviewer (reviewer_id, reviewed_at),
  ADD CONSTRAINT fk_practice_records_assignment
    FOREIGN KEY (assignment_id) REFERENCES assignments (id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT fk_practice_records_assignment_attempt
    FOREIGN KEY (assignment_attempt_id) REFERENCES assignment_attempts (id)
    ON DELETE SET NULL ON UPDATE CASCADE,
  ADD CONSTRAINT fk_practice_records_reviewer
    FOREIGN KEY (reviewer_id) REFERENCES users (id)
    ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE user_notifications
  ADD COLUMN action_url VARCHAR(512) NULL AFTER content;
