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
  `live_id` int DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` int NOT NULL,
  `id` bigint DEFAULT NULL,
  `name` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  `select_difficulty` int DEFAULT NULL,
  PRIMARY KEY (`room_id`)
);