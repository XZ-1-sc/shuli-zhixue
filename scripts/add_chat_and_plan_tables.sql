USE xingce;

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
