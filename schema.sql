use webapp;

DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `rooms`;
CREATE TABLE `rooms` (
  `room_id` int NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `room_state` int NOT NULL DEFAULT 1,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` int NOT NULL,
  `user_id` int NOT NULL,
  `is_host` boolean NOT NULL DEFAULT 0,
  `score` int,
  `difficulty` int,
  `perfect` int,
  `great` int,
  `good` int,
  `bad` int,
  `miss` int,
  PRIMARY KEY (`room_id`, `user_id`)
);
