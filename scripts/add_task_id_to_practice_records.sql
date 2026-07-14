USE xingce;

ALTER TABLE practice_records
  ADD COLUMN task_id VARCHAR(64) NOT NULL DEFAULT 'default_task' COMMENT '练习任务ID' AFTER id,
  ADD KEY idx_practice_records_task (task_id),
  ADD KEY idx_practice_records_user_task (user_id, task_id);
