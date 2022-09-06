DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `token` varchar(255) NOT NULL,
  `leader_card_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `token` (`token`)
);

DROP TABLE IF EXISTS `room`;
CREATE TABLE `room` (
  `room_id` bigint NOT NULL AUTO_INCREMENT,
  `live_id` int  NOT NULL,
  `owner_id` bigint NOT NULL,
  `joined_user_count` int  NOT NULL,
  `max_user_count` int  NOT NULL,
  `wait_room_status` int NOT NULL,
  
  PRIMARY KEY (`room_id`)
);

DROP TABLE IF EXISTS `room_member`;
CREATE TABLE `room_member` (
  `room_id` bigint NOT NULL,
  `user_id` bigint NOT NULL,
  `score` int,
  `select_difficulty` int NOT NULL,
  `judge_count_list` varchar(255),
  
  PRIMARY KEY (`room_id`, `user_id`)
);