USE math_brain;

ALTER TABLE uploaded_files
  MODIFY COLUMN mime_type VARCHAR(160) NOT NULL;

CREATE TABLE IF NOT EXISTS user_notes (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(160) NOT NULL,
  content TEXT NOT NULL,
  course VARCHAR(128) NULL,
  knowledge_tag VARCHAR(160) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_user_notes_user_time (user_id, updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS note_attachments (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  note_id BIGINT UNSIGNED NOT NULL,
  uploaded_file_id BIGINT UNSIGNED NOT NULL,
  sort_order TINYINT UNSIGNED NOT NULL DEFAULT 1,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_note_attachments_file (uploaded_file_id),
  KEY idx_note_attachments_note (note_id, sort_order),
  CONSTRAINT fk_note_attachments_note
    FOREIGN KEY (note_id) REFERENCES user_notes (id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_note_attachments_file
    FOREIGN KEY (uploaded_file_id) REFERENCES uploaded_files (id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
