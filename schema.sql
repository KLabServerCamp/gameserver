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
  `live_id` int DEFAULT NULL,
  `room_id` int DEFAULT NULL,
  `joined_user_count` int DEFAULT NULL,
  `max_user_count` int DEFAULT NULL,
  `status` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `room_id` (`room_id`)
);


DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) DEFAULT NULL,
  `room_id` int DEFAULT NULL,
  `is_host` boolean DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `room_id` (`room_id`)
);
