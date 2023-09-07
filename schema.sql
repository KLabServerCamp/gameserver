use webapp;

DROP TABLE IF EXISTS `room_member`;
DROP TABLE IF EXISTS `room`;
DROP TABLE IF EXISTS `user`;

CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL DEFAULT 1,
  `max_user_count` int NOT NULL DEFAULT 4,
  `select_difficulty` int NOT NULL,
  PRIMARY KEY (`room_id`)
);

CREATE TABLE `room_member` (
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` BOOLEAN NOT NULL DEFAULT FALSE,
  `judge_count_list` json, 
  `score` int,
  FOREIGN KEY (`user_id`) REFERENCES `user`(`id`),
  FOREIGN KEY (`room_id`) REFERENCES `room`(`room_id`)
);