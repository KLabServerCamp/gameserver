use webapp;

-- DROP TABLE IF EXISTS `user`;
-- CREATE TABLE `user` (
--   `id` bigint NOT NULL AUTO_INCREMENT,
--   `name` varchar(255) NOT NULL,
--   `token` varchar(255) NOT NULL,
--   `leader_card_id` int NOT NULL,
--   PRIMARY KEY (`id`),
--   UNIQUE KEY `token` (`token`)
-- );

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` bigint NOT NULL,
  `joined_user_count` int DEFAULT 1 NOT NULL,
  `max_user_count` int DEFAULT 4 NOT NULL,
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `member_list` varchar(255),
  PRIMARY KEY (`room_id`),
  UNIQUE KEY `room_id` (`room_id`)
);

DROP TABLE IF EXISTS `room_user`;
CREATE TABLE `room_user` (
  `user_id` bigint NOT NULL, 
  `room_id` bigint NOT NULL,
  `select_difficulty` int NOT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_id` (`user_id`)
);