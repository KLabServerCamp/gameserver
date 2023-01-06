DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);


DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL DEFAULT 1,
  `max_user_count` int NOT NULL,
  `is_playing` boolean NOT NULL DEFAULT 0,
  `time_to_live` BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (`room_id`)
);


DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `judge_count_list` varchar(255) DEFAULT NULL,
  `score` int DEFAULT 0,
  `result_shown` boolean NOT NULL DEFAULT 0,
  `time_to_live` BIGINT UNSIGNED NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);

