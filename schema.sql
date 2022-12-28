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
  `room_id` int NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `owner_id` bigint NOT NULL,
  `status` int NOT NULL,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `select_difficulty` int,
  `score` int,
  `judge` varchar(255),
  PRIMARY KEY (`room_id`, `user_id`)
);