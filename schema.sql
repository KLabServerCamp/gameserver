DROP TABLE IF EXISTS `user`;
DROP TABLE IF EXISTS `room`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL DEFAULT 1,
  `max_user_count` int NOT NULL DEFAULT 4,
  PRIMARY KEY (`id`)
);
CREATE TABLE `room_member` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `room_id` bigint NOT NULL,
  `user_id` int NOT NULL,
  `name` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  `select_difficulty` int NOT NULL,
  `is_host` boolean NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`)
);
