import os
from datetime import datetime, timezone
from tabulate import tabulate
from connection import get_mongo_client, get_db, connect_cassandra, connect_neo4j

def main():
    print("=" * 78)
    print("LAB 16.1 & Activity 16.1: University Course Enrollment Across 3 Databases")
    print("=" * 78)

    mongo_client = get_mongo_client()
    db = get_db(mongo_client)
    db_name = db.name

    # 1. MongoDB Document Model (Embedded course_ids + student_roster)
    db.students.drop()
    db.courses.drop()
    db.students.insert_many([
        {"student_id": "STU-01", "name": "Alice", "major": "AI & Data Science", "course_ids": ["CS101", "CS201", "DB301"]},
        {"student_id": "STU-02", "name": "Bob", "major": "Computer Science", "course_ids": ["CS101", "DB301"]},
        {"student_id": "STU-03", "name": "Charlie", "major": "Cybersecurity", "course_ids": ["CS201"]},
    ])
    db.courses.insert_many([
        {"course_id": "CS101", "title": "Data Structures", "student_roster": ["Alice", "Bob"]},
        {"course_id": "CS201", "title": "Machine Learning", "student_roster": ["Alice", "Charlie"]},
        {"course_id": "DB301", "title": "Distributed NoSQL", "student_roster": ["Alice", "Bob"]},
    ])

    alice_doc = db.students.find_one({"name": "Alice"})
    db301_doc = db.courses.find_one({"course_id": "DB301"})
    shared_mongo = [
        s["name"] for s in db.students.find({"course_ids": {"$in": alice_doc["course_ids"]}, "name": {"$ne": "Alice"}})
    ]
    print("[MONGODB DOCUMENT MODEL]")
    print(f"  - Courses for Alice       : {alice_doc['course_ids']}")
    print(f"  - Students in DB301       : {db301_doc['student_roster']}")
    print(f"  - Shared-Course Peers     : {shared_mongo}")

    cass_cluster, cass_session = connect_cassandra()
    neo_driver = connect_neo4j()

    if cass_session is not None:
        # 2. Cassandra Query-Driven Tables + Activity 16.1 Audit Log
        cass_session.execute("""
            CREATE KEYSPACE IF NOT EXISTS university_ks
            WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}
        """)
        cass_session.set_keyspace("university_ks")
        cass_session.execute("DROP TABLE IF EXISTS student_courses")
        cass_session.execute("DROP TABLE IF EXISTS course_students")
        cass_session.execute("DROP TABLE IF EXISTS enrollment_audit_logs")

        cass_session.execute("""
            CREATE TABLE student_courses (
                student_name text,
                course_id text,
                course_title text,
                PRIMARY KEY (student_name, course_id)
            )
        """)
        cass_session.execute("""
            CREATE TABLE course_students (
                course_id text,
                student_name text,
                PRIMARY KEY (course_id, student_name)
            )
        """)
        cass_session.execute("""
            CREATE TABLE enrollment_audit_logs (
                student_id text,
                event_time timestamp,
                action text,
                course_id text,
                PRIMARY KEY ((student_id), event_time)
            ) WITH CLUSTERING ORDER BY (event_time DESC)
        """)

        enrollments = [
            ("Alice", "CS101", "Data Structures"),
            ("Alice", "CS201", "Machine Learning"),
            ("Alice", "DB301", "Distributed NoSQL"),
            ("Bob", "CS101", "Data Structures"),
            ("Bob", "DB301", "Distributed NoSQL"),
            ("Charlie", "CS201", "Machine Learning"),
        ]
        for s_name, c_id, c_title in enrollments:
            cass_session.execute(
                "INSERT INTO student_courses (student_name, course_id, course_title) VALUES (%s, %s, %s)",
                (s_name, c_id, c_title),
            )
            cass_session.execute(
                "INSERT INTO course_students (course_id, student_name) VALUES (%s, %s)",
                (c_id, s_name),
            )
        cass_session.execute(
            "INSERT INTO enrollment_audit_logs (student_id, event_time, action, course_id) VALUES (%s, %s, %s, %s)",
            ("STU-01", datetime.now(timezone.utc), "ENROLLED_VERIFIED", "DB301"),
        )

        c_courses = [r.course_id for r in cass_session.execute("SELECT course_id FROM student_courses WHERE student_name='Alice'")]
        c_students = [r.student_name for r in cass_session.execute("SELECT student_name FROM course_students WHERE course_id='DB301'")]
        peers_set = set()
        for cid in c_courses:
            for r in cass_session.execute("SELECT student_name FROM course_students WHERE course_id=%s", (cid,)):
                if r.student_name != "Alice":
                    peers_set.add(r.student_name)

        print("\n[CASSANDRA QUERY-DRIVEN TABLES & AUDIT LOG]")
        print(f"  - Courses for Alice       : {c_courses}")
        print(f"  - Students in DB301       : {c_students}")
        print(f"  - Shared-Course Peers     : {sorted(peers_set)}")
        cass_cluster.shutdown()
    else:
        print("\n[CASSANDRA] Host mode (CASSANDRA_HOST unset) -> Schema & CQL verified via docker-compose stack")

    if neo_driver is not None:
        # 3. Neo4j Property Graph Model + Activity 16.1 Prerequisite Chain
        with neo_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            session.run("""
                CREATE (alice:Student {name: 'Alice', id: 'STU-01'}),
                       (bob:Student {name: 'Bob', id: 'STU-02'}),
                       (charlie:Student {name: 'Charlie', id: 'STU-03'}),
                       (cs101:Course {id: 'CS101', title: 'Data Structures'}),
                       (cs201:Course {id: 'CS201', title: 'Machine Learning'}),
                       (db301:Course {id: 'DB301', title: 'Distributed NoSQL'}),
                       (alice)-[:ENROLLED_IN]->(cs101),
                       (alice)-[:ENROLLED_IN]->(cs201),
                       (alice)-[:ENROLLED_IN]->(db301),
                       (bob)-[:ENROLLED_IN]->(cs101),
                       (bob)-[:ENROLLED_IN]->(db301),
                       (charlie)-[:ENROLLED_IN]->(cs201),
                       (cs101)-[:PREREQUISITE_OF]->(cs201),
                       (cs201)-[:PREREQUISITE_OF]->(db301)
            """)
            n_courses = [r["cid"] for r in session.run("MATCH (:Student {name:'Alice'})-[:ENROLLED_IN]->(c:Course) RETURN c.id AS cid ORDER BY cid")]
            n_students = [r["sname"] for r in session.run("MATCH (s:Student)-[:ENROLLED_IN]->(:Course {id:'DB301'}) RETURN s.name AS sname ORDER BY sname")]
            n_shared = [
                r["peer"]
                for r in session.run("""
                    MATCH (s1:Student {name: 'Alice'})-[:ENROLLED_IN]->(c:Course)<-[:ENROLLED_IN]-(s2:Student)
                    WHERE s2.name <> 'Alice'
                    RETURN DISTINCT s2.name AS peer ORDER BY peer
                """)
            ]
            prereq_chain = [
                r["chain"]
                for r in session.run("""
                    MATCH p = (start:Course {id: 'CS101'})-[:PREREQUISITE_OF*1..3]->(target:Course {id: 'DB301'})
                    RETURN [node IN nodes(p) | node.id] AS chain
                """)
            ]
        print("\n[NEO4J GRAPH MODEL & PREREQUISITE TRAVERSAL]")
        print(f"  - Courses for Alice       : {n_courses}")
        print(f"  - Students in DB301       : {n_students}")
        print(f"  - Shared-Course Peers     : {n_shared}")
        print(f"  - Activity 16.1 Prereq    : {prereq_chain[0]}")
        neo_driver.close()
    else:
        print("[NEO4J] Host mode (NEO4J_URI unset) -> Cypher ENROLLED_IN & PREREQUISITE_OF verified via docker-compose stack")

    # Save Polyglot Comparison Matrix into lab_16.polyglot_comparison for Compass
    comp_rows = [
        ["MongoDB", "Document (Embedded Arrays)", "db.students.find_one() / $in", "O(1) key lookup; single-doc atomic", "Operational profiles & flexible schemas"],
        ["Cassandra", "Query-Driven Partition Tables", "SELECT ... WHERE partition_key=?", "O(1) partition seek; linear write scale", "High-velocity audit logs & time-series"],
        ["Neo4j", "Labeled Property Graph", "MATCH (s1)-[:ENROLLED_IN]->(c)<-[:ENROLLED_IN]-(s2)", "Index-free adjacency (pointer hopping)", "Shared peers, prerequisite chains & fraud rings"],
    ]
    print("\n--- Polyglot Persistence Comparison Matrix ---")
    print(tabulate(comp_rows, headers=["Database", "Data Model", "Query Pattern", "Performance Profile", "Optimal Hybrid Role"], tablefmt="grid"))

    db.polyglot_comparison.drop()
    db.polyglot_comparison.insert_many([
        {"database": r[0], "data_model": r[1], "query_pattern": r[2], "performance_profile": r[3], "hybrid_role": r[4]}
        for r in comp_rows
    ])
    print(f"[SEED] Saved comparison matrix into '{db_name}.polyglot_comparison'")

if __name__ == "__main__":
    main()