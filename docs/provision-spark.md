# PySpark

PySpark DataFrame is the abstraction layer (build from Python) that able to
interact with spark cluster compute.

## Prerequisites

### Create Spark Cluster

#### Use Docker Compose

* Provision the Docker containers

  ```console
  $ docker-compose up -d --scale spark-worker=3
  ```

* Testing run job

  ```console
  $ docker exec spark-master \
      spark-submit \
      --master spark://spark-master:7077 \
      --deploy-mode client \
      /mounted-data/src/ddeutil/pyspark/main.py
  ```

#### Use Local Standalone

> **Warning**: \
> This option has issue of Java version on Local Machine

* Install Java, check version of Java, `java -version`, and set path `JAVA_HOME`
* [Install Spark](https://spark.apache.org/downloads.html) to `/spark-x.x.x-bin-hadoopX`,
  set path `SPARK_HOME` to this folder and add bin to PATH
* [Download `winutils.exe`](https://github.com/steveloughran/winutils/blob/master/hadoop-3.0.0/bin/winutils.exe)
  to `/hadoop/bin`, set path `HADOOP_HOME=/hadoop` and add bin to PATH
* Install `pyspark` package

## Features
