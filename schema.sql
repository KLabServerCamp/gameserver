DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);


DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int DEFAULT NULL,
  `joined_user_count` int DEFAULT NULL,
  `max_user_count` int DEFAULT NULL,
  `is_playing` boolean DEFAULT 0
  PRIMARY KEY (`room_id`)
);


DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `judge_count_list` int DEFAULT NULL,
  `score` int DEFAULT 0,
  PRIMARY KEY (`room_id`, `user_id`)
);

