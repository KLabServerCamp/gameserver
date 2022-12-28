DROP TABLE IF EXISTS `room_member`;

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
  `id` bigint NOT NULL AUTO_INCREMENT,
  `owner_id` bigint NOT NULL,
  `live_id` int NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `room_member` (
  `user_id` bigint NOT NULL,
  `room_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  PRIMARY KEY (`room_id`, `user_id`)
);