import request from '@/utils/request'

export const getAdminListService = () => {
  return request.get('/admin/getAdminList')
}

//学生管理
export const getStudentListService = (params) => {
  return request.get('api/admin/users', {
    params: {
      search: params.search, // 从对象中取search
      page: params.page,       // 从对象中取 page
      role: 'student'
    }
  })
}

export const updateStudentPasswordService = (id, password) => {
  return request.put(`api/admin/users/student/${id}/reset-password`, null, {
    params: { password }  // 明确将password作为查询参数
  })
};

export const updateTeacherPasswordService = (id, password) => {
  return request.put(`api/admin/users/teacher/${id}/reset-password`, null, {
    params: { password }  // 明确将password作为查询参数
  })
};

export const addStudentService = (username,password) => {
  return request.post('api/admin/users',  {
      username,
      password,
      role:'student'
  })
}

export const editStudentService = (username,password) => {
  return request.put('api/admin/editStudent', {
      username,
      password,
      role:'student'
  })
}

export const deleteStudentService = (id) => {
  return request.delete(`api/admin/users/student/${id}`);
}

//教师管理
export const getTeacherListService = (params) => {
  return request.get('api/admin/users', {
    params: {
      search: params.search, // 从对象中取search
      page: params.page,       // 从对象中取 page
      role: 'teacher'
    }
  })
}

export const addTeacherService = (username,password) => {
  return request.post('api/admin/users',  {
      username,
      password,
      role:'teacher'
  })
}

export const editTeacherService = (teacher) => {
  return request.put('/admin/editTeacher', teacher)
}

export const deleteTeacherService = (id) => {
  return request.delete(`api/admin/users/teacher/${id}`);
}

export const getSubjectListService = () => {
  return request.get('api/admin/subjects')
}

export const getTeachingPlansService = (subject) => {
  return request.get(`api/admin/resources/by-subject/${subject}`);
}

export const getPlanContentService = (resource_type,resource_id) => {
  return request.get(`api/admin/resources/${resource_type}/${resource_id}`);
}

export const exportwenjian = (resource_type,resource_id) => {
  return request.get(`api/admin/resources/${resource_type}/${resource_id}/export`);
}

export const getActivityDataService = () => {
  return request.get('/api/admin/dashboard/usage-stats'); 
};

export const getTeachEffectDataService = () => {
  return request.get('/api/admin/dashboard/teaching-efficiency'); 
};

export const getlowperformingsubjectsService = () => {
  return request.get('/api/admin/dashboard/low-performing-subjects'); 
};

export const getLearningEffectService = () => {
  return request.get('/api/admin/dashboard/student-effectiveness'); 
};