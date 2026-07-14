USE xingce;

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
