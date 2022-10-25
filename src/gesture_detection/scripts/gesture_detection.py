#!/home/pumid/Desktop/athome/bin/python3

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, PointCloud2
from cv_bridge import CvBridge
import cv2 as cv
import numpy as np
import mediapipe as mp
from utils import CvFpsCalc
from collections import deque
import os
from model import KeyPointClassifier
import copy
import itertools
print(os.getcwd())
 
class GestureDetection(Node):
    def __init__(self):
        super().__init__('gesture_detection')
        self.subscription = self.create_subscription(Image, '/camera/color/image_raw', self.listener_callback, 10)
        self.pointclound = self.create_subscription(PointCloud2, '/camera/depth/color/points', self.pointclound_callback, 10)
        self.br = CvBridge()
        
        self.mp_drawing_styles = mp.solutions.drawing_styles
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=False,
                                         max_num_hands=1,
                                         min_detection_confidence=0.7,
                                         min_tracking_confidence=0.5,)

        self.keypoint_classifier = KeyPointClassifier()
        self.keypoint_classifier_labels = ['Open', 'Close', 'Pointer', 'OK']

        self.cvFpsCalc = CvFpsCalc(buffer_len=10)
        self.fps_que = deque(maxlen=16)

        
    def listener_callback(self, data):
        self.img = self.br.imgmsg_to_cv2(data)
        self.img = cv.resize(self.img, [960, 540])
        self.img = cv.flip(self.img, 1)
        self.cp_img = copy.deepcopy(self.img)
        self.img = cv.cvtColor(self.img, cv.COLOR_BGR2RGB)

        fps = self.cvFpsCalc.get()
        self.fps_que.append(fps)
        self.detectGesture()
        self.get_logger().info('Receiving video frame')
        cv.putText(self.cp_img, "FPS:" + str(fps), (10, 30), cv.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4, cv.LINE_AA)
        cv.putText(self.cp_img, "FPS:" + str(fps), (10, 30), cv.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv.LINE_AA)
        print("FPS: " + str(fps))
        cv.imshow('Raw Webcam Feed', self.cp_img)
        cv.waitKey(1)

    def detectGesture(self):
        self.img.flags.writeable = False
        results = self.hands.process(self.img)
        self.img.flags.writeable = True
        if results.multi_hand_landmarks:
            for hand_landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                landmark_point = []
                for _, landmark in enumerate(hand_landmarks.landmark):
                    landmark_point.append([landmark.x, landmark.y, landmark.z])
                landmark_list = self.calc_landmark_list(hand_landmarks)
                pre_processed_landmark_list = self.pre_process_landmark(landmark_list)
                hand_sign_id = self.keypoint_classifier(pre_processed_landmark_list)

                ##### disply #####
                self.mp_drawing.draw_landmarks( self.cp_img, 
                                                hand_landmarks, 
                                                self.mp_hands.HAND_CONNECTIONS,
                                                self.mp_drawing_styles.get_default_hand_landmarks_style(), 
                                                self.mp_drawing_styles.get_default_hand_connections_style())

                brect = self.calc_bounding_rect(hand_landmarks)
                cv.rectangle(self.cp_img, (brect[0], brect[1]), (brect[2], brect[3]), (0, 0, 0), 1)
                cv.rectangle(self.cp_img, (brect[0], brect[1]), (brect[2], brect[1] - 22),(0, 0, 0), -1)
                hand_sign_text = self.keypoint_classifier_labels[hand_sign_id]
                print("hand_sign_id: " + str(hand_sign_id))
                info_text = handedness.classification[0].label[0:]
                if hand_sign_text != "":
                    info_text = info_text + ':' + hand_sign_text
                cv.putText(self.cp_img, info_text, (brect[0] + 5, brect[1] - 4), cv.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv.LINE_AA)

    def calc_landmark_list(self, landmarks):
        image_width, image_height = self.cp_img.shape[1], self.cp_img.shape[0]
        landmark_point = []
        for _, landmark in enumerate(landmarks.landmark):
            landmark_x = min(int(landmark.x * image_width), image_width - 1)
            landmark_y = min(int(landmark.y * image_height), image_height - 1)
            landmark_point.append([landmark_x, landmark_y])

        return landmark_point

    def pre_process_landmark(self, landmark_list):
        temp_landmark_list = copy.deepcopy(landmark_list)

        # Convert to relative coordinates
        base_x, base_y = 0, 0
        for index, landmark_point in enumerate(temp_landmark_list):
            if index == 0:
                base_x, base_y = landmark_point[0], landmark_point[1]

            temp_landmark_list[index][0] = temp_landmark_list[index][0] - base_x
            temp_landmark_list[index][1] = temp_landmark_list[index][1] - base_y

        # Convert to a one-dimensional list
        temp_landmark_list = list(
            itertools.chain.from_iterable(temp_landmark_list))

        # Normalization
        max_value = max(list(map(abs, temp_landmark_list)))

        def normalize_(n):
            return n / max_value

        temp_landmark_list = list(map(normalize_, temp_landmark_list))

        return temp_landmark_list

    def calc_bounding_rect(self, landmarks):
        image_width, image_height = self.cp_img.shape[1], self.cp_img.shape[0]

        landmark_array = np.empty((0, 2), int)

        for _, landmark in enumerate(landmarks.landmark):
            landmark_x = min(int(landmark.x * image_width), image_width - 1)
            landmark_y = min(int(landmark.y * image_height), image_height - 1)

            landmark_point = [np.array((landmark_x, landmark_y))]

            landmark_array = np.append(landmark_array, landmark_point, axis=0)

        x, y, w, h = cv.boundingRect(landmark_array)

        return [x, y, x + w, y + h]


    def pointclound_callback(self, whaty):
        pass

def main(args=None):
    rclpy.init(args=args)
    gesture_detection = GestureDetection()
    rclpy.spin(gesture_detection)
    gesture_detection.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
  main()