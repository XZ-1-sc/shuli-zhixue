USE xingce;

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
