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
  `live_id` bigint NOT NULL,
  `owner_token` varchar(255) DEFAULT NULL,
  `joined_user_count` bigint NOT NULL,
  `max_user_count` bigint NOT NULL,
  PRIMARY KEY (`id`)
);


DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `token` varchar(255) DEFAULT NULL,
  `room_id` bigint NOT NULL,
  `select_difficulty` bigint NOT NULL,
  PRIMARY KEY (`id`)
);
