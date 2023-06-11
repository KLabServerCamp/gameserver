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
  `room_id` int NOT NULL AUTO_INCREMENT,
  `live_id` int NOT NULL,
  `joined_user_count` int NOT NULL,
  `max_user_count` int NOT NULL DEFAULT 4,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `user_id` bigint NOT NULL ,
  `room_id` int NOT NULL,
  `name` varchar(255) NOT NULL ,
  `leader_card_id` int NOT NULL,
  `select_diffculty` int NOT NULL,
  `is_me` boolean NOT NULL,
  `is_host` boolean NOT NULL,
  PRIMARY KEY (`user_id`)
);
