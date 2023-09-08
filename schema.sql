use webapp;

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
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL,
  `max_user_count` int NOT NULL,
  `game_is_start` boolean DEFAULT FALSE,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,  
  `user_id` bigint NOT NULL,
  `difficulty` int NOT NULL,
  `is_host` boolean DEFAULT FALSE,
  `judge_count_list` json DEFAULT NULL,
  `score` bigint DEFAULT NULL, 
  PRIMARY KEY (`room_id`, `user_id`)
);