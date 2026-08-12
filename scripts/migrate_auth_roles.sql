USE math_brain;

-- Run only when the users table does not yet contain the role column.
ALTER TABLE users
  ADD COLUMN role ENUM('student', 'teacher', 'admin')
  NOT NULL DEFAULT 'student' AFTER email;

CREATE INDEX idx_users_role_status ON users (role, status);

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
