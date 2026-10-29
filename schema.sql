-- Postgres schema for class_dataset.csv.
-- Tools and availability slots are reference data and are seeded here.
-- Student rows are not loaded by this file.
-- Safe to run more than once.

begin;

do $$
begin
    create type identifier_kind as enum ('netid', 'email', 'n_number');
exception
    when duplicate_object then null;
end $$;

-- CSV values map as: First-year -> first_year, Sophomore -> sophomore,
-- Junior -> junior, Senior -> senior.
do $$
begin
    create type school_year as enum ('first_year', 'sophomore', 'junior', 'senior');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type intro_programming as enum ('took_it', 'equivalent', 'neither');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type day_part as enum ('weekday', 'weekend');
exception
    when duplicate_object then null;
end $$;

do $$
begin
    create type time_of_day as enum ('morning', 'afternoon', 'evening');
exception
    when duplicate_object then null;
end $$;

create table if not exists students (
    id integer generated always as identity primary key,
    -- Trimmed original value. Kind is separate because the column mixes
    -- netids (jq2306), emails (yo2162@nyu.edu), and N-numbers (N16059079).
    identifier text not null unique check (length(trim(identifier)) > 0),
    identifier_kind identifier_kind not null,
    name text not null check (length(trim(name)) > 0),
    school_year school_year not null,
    intro_programming intro_programming not null,
    skill_programming smallint not null check (skill_programming between 1 and 5),
    skill_data_stats smallint not null check (skill_data_stats between 1 and 5),
    skill_frontend_design smallint not null check (skill_frontend_design between 1 and 5),
    skill_business_pitch smallint not null check (skill_business_pitch between 1 and 5),
    -- Free text. An Excel #NAME? error in the source is stored as null.
    working_style text,
    interests text,
    semester_goal text,
    submitted_at timestamptz not null
);

create table if not exists tools (
    id integer generated always as identity primary key,
    name text not null unique
);

create table if not exists student_tools (
    student_id integer not null references students (id) on delete cascade,
    tool_id integer not null references tools (id) on delete cascade,
    primary key (student_id, tool_id)
);

create table if not exists availability_slots (
    id integer generated always as identity primary key,
    day_part day_part not null,
    time_of_day time_of_day not null,
    unique (day_part, time_of_day)
);

create table if not exists student_availability (
    student_id integer not null references students (id) on delete cascade,
    slot_id integer not null references availability_slots (id) on delete cascade,
    primary key (student_id, slot_id)
);

insert into tools (name) values
    ('Python'),
    ('SQL'),
    ('Excel'),
    ('JavaScript'),
    ('R')
on conflict (name) do nothing;

insert into availability_slots (day_part, time_of_day) values
    ('weekday', 'morning'),
    ('weekday', 'afternoon'),
    ('weekday', 'evening'),
    ('weekend', 'morning'),
    ('weekend', 'afternoon'),
    ('weekend', 'evening')
on conflict (day_part, time_of_day) do nothing;

commit;
