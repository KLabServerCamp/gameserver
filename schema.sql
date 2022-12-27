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
  `joined_user_count` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`room_id`)
);


DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `leader_card_id` int DEFAULT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  `score` int DEFAULT 0,
  `end_playing` boolean NOT NULL DEFAULT false,
  PRIMARY KEY (`room_id`, `user_id`)
);
