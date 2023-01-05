DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `token` varchar(255) DEFAULT NULL,
  `leader_card_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);
CREATE TABLE `room` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint DEFAULT NULL,
  `oener` bigint DEFAULT NULL,
  `status` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
);
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint DEFAULT NULL,
  `score` bigint DEFAULT NULL,
  `judge` varchar(255) DEFAULT NULL,
  `difficulty` bigint DEFAULT NULL,
  `is_join` bigint DEFAULT NULL,
  PRIMARY KEY (`room_id`),
);